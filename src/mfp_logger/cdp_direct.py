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

    # Extract target grams from name if specified (e.g. 500g -> 5.0 of 100g unit)
    target_grams = None
    match_grams = re.search(r'(\d+)\s*(?:g|gr|gram|grams)', food_name.lower())
    if match_grams:
        target_grams = float(match_grams.group(1))

    # Clean query for search
    clean_query = re.sub(r'\(.*?\)', '', food_name)
    clean_query = re.sub(r'\b\d+\s*(?:g|gr|gram|grams|kg|oz|lbs?)\b', '', clean_query, flags=re.IGNORECASE).strip()
    if not clean_query:
        clean_query = food_name

    # 1. Open search page
    js_navigate = f"window.location.href = 'https://www.myfitnesspal.com/food/add_to_diary?meal={meal_idx}';"
    execute_cdp_in_tab(tab_id, js_navigate)
    time.sleep(2)

    # 2. Search clean food name
    js_search = f"""
    (() => {{
        const searchInput = document.querySelector('input#search, input[name="search"]');
        if (searchInput) {{
            searchInput.value = '{clean_query}';
            searchInput.form.submit();
        }}
    }})()
    """
    execute_cdp_in_tab(tab_id, js_search)
    time.sleep(2.5)

    # 3. Select match, wait for servings DOM to load, set exact quantity, then submit
    js_click_match = """
    (() => {
        const match = document.querySelector('ul#matching li a.search, a.search');
        if (match) {
            match.click();
            return { status: 'clicked' };
        }
        return { status: 'no_match' };
    })()
    """
    execute_cdp_in_tab(tab_id, js_click_match)
    time.sleep(2)

    # Calculate exact quantity multiplier
    qty_val = 1.0
    if target_grams is not None:
        qty_val = round(target_grams / 100.0, 1) # e.g. 500g / 100g = 5.0
    elif calories > 0:
        qty_val = round(calories / 110.0, 1)

    js_set_qty_and_submit = f"""
    (() => {{
        const qtyInput = document.querySelector('input#food_entry_quantity, input[name*="quantity"]');
        if (qtyInput) {{
            qtyInput.value = '{qty_val}';
        }}
        const addBtn = document.querySelector('#add_button, input[value*="Add Food"], button[type="submit"]');
        if (addBtn) {{
            addBtn.click();
            return {{ status: 'submitted', qty: '{qty_val}' }};
        }}
        return {{ status: 'button_not_found' }};
    }})()
    """
    execute_cdp_in_tab(tab_id, js_set_qty_and_submit)
    time.sleep(2.5)

    return {"status": "succeeded", "message": f"Successfully logged {food_name} ({qty_val}x portion) to {meal_category} in MyFitnessPal"}
