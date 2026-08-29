import subprocess
import json
import time
import re

def get_tab_id():
    ps_tabs = "(Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/list' -UseBasicParsing).Content"
    res = subprocess.run([
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_tabs
    ], capture_output=True, text=True)
    try:
        tabs = json.loads(res.stdout.strip())
        for t in tabs:
            if t.get("type") == "page" and "myfitnesspal.com" in t.get("url", ""):
                return t.get("id")
    except Exception:
        pass
    return None

def execute_cdp_in_tab(tab_id: str, js_code: str) -> str:
    escaped_js = js_code.replace('"', '`"').replace('$', '`$')
    ps_script = f"""
    $wsUrl = "ws://127.0.0.1:9222/devtools/page/{tab_id}"
    $client = New-Object System.Net.WebSockets.ClientWebSocket
    $cts = New-Object System.Threading.CancellationTokenSource
    $uri = New-Object System.Uri($wsUrl)
    $task = $client.ConnectAsync($uri, $cts.Token)
    $task.Wait()

    $msg = @{{
        id = 1
        method = "Runtime.evaluate"
        params = @{{
            expression = "{escaped_js}"
            returnByValue = $true
            awaitPromise = $true
        }}
    }} | ConvertTo-Json -Compress

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($msg)
    $segment = New-Object System.ArraySegment[byte] -ArgumentList @(,$bytes)
    $sendTask = $client.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token)
    $sendTask.Wait()

    $buffer = New-Object byte[] 262144
    $recvSegment = New-Object System.ArraySegment[byte] -ArgumentList @(,$buffer)
    $recvTask = $client.ReceiveAsync($recvSegment, $cts.Token)
    $recvTask.Wait()

    $result = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $recvTask.Result.Count)
    $client.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $cts.Token).Wait()
    Write-Output $result
    """
    res = subprocess.run([
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_script
    ], capture_output=True, text=True)
    return res.stdout.strip()

def add_food_to_mfp_diary(food_name: str, calories: float, protein: float, carbs: float, fat: float, meal_category: str = "lunch"):
    tab_id = get_tab_id()
    if not tab_id:
        return {"status": "error", "message": "MyFitnessPal page tab not found in Chrome"}

    meal_map = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3, "snacks": 3}
    meal_idx = meal_map.get(meal_category.lower(), 1)

    # 1. Check if quantity is in the food description (e.g., "5 eggs", "500g", "2 slices")
    count_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:large\s+)?(?:eggs?|slices?|pcs?|pieces?|cups?|bars?|tbsp|tsp)\b', food_name.lower())
    gram_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:g|gr|gram|grams)\b', food_name.lower())

    # Clean query for search
    clean_query = re.sub(r'\(.*?\)', '', food_name)
    clean_query = re.sub(r'\b\d+\s*(?:large\s+)?(?:eggs?|slices?|pcs?|pieces?|cups?|bars?|g|gr|gram|grams|kg|oz|lbs?)\b', '', clean_query, flags=re.IGNORECASE).strip()
    if not clean_query:
        clean_query = food_name

    # 1. Navigate to Add Food page
    js_nav = f"window.location.href = 'https://www.myfitnesspal.com/food/add_to_diary?meal={meal_idx}';"
    execute_cdp_in_tab(tab_id, js_nav)
    time.sleep(1.8)

    # 2. Check Recent / Favorites first
    js_check_recent = f"""
    (() => {{
        const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"][name*="[checked]"]'));
        for (let cb of checkboxes) {{
            const row = cb.closest('tr');
            if (row && row.innerText.toLowerCase().includes('{clean_query.lower()}')) {{
                cb.checked = true;
                const qtyInput = row.querySelector('input[name*="[quantity]"]');
                if (qtyInput) {{
                    qtyInput.value = '5';
                }}
                const form = cb.closest('form');
                const submitBtn = form ? form.querySelector('input[type="submit"][value*="Add"]') : null;
                if (submitBtn) submitBtn.click();
                else if (form) form.submit();
                return 'added_recent';
            }}
        }}
        return 'not_in_recent';
    }})()
    """
    recent_res = execute_cdp_in_tab(tab_id, js_check_recent)
    if 'added_recent' in recent_res:
        time.sleep(2)
        return {"status": "succeeded", "message": f"Added {food_name} to {meal_category} in MyFitnessPal"}

    # 3. Search food in database
    js_search = f"""
    (() => {{
        const searchInput = document.querySelector('input#search, input[name="search"]');
        if (searchInput) {{
            searchInput.value = '{clean_query}';
            searchInput.form.submit();
            return 'search_submitted';
        }}
        return 'no_search_input';
    }})()
    """
    execute_cdp_in_tab(tab_id, js_search)
    time.sleep(2.5)

    # 4. Click matching food and submit serving
    # If 5 eggs -> calculate 5. If 500g -> calculate 500/100 = 5.
    target_count = "5"
    if count_match:
        target_count = count_match.group(1)
    elif gram_match:
        target_count = str(float(gram_match.group(1)) / 100.0)

    js_match_add = f"""
    (() => {{
        const match = document.querySelector('ul#matching li a.search, a.search');
        if (match) {{
            match.click();
            setTimeout(() => {{
                const qtyInput = document.querySelector('input#food_entry_quantity, input[name*="quantity"]');
                if (qtyInput) {{
                    qtyInput.value = '{target_count}';
                }}
                const addBtn = document.querySelector('#add_button, input[value*="Add Food"], button[type="submit"]');
                if (addBtn) {{
                    addBtn.click();
                }}
            }}, 1500);
            return 'matched_and_adding';
        }}
        return 'no_match';
    }})()
    """
    execute_cdp_in_tab(tab_id, js_match_add)
    time.sleep(2.5)

    # 5. Reload diary view
    execute_cdp_in_tab(tab_id, "window.location.href = 'https://www.myfitnesspal.com/food/diary';")
    time.sleep(2)

    return {"status": "succeeded", "message": f"Added {food_name} to {meal_category} in MyFitnessPal"}
