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

    # Extract target piece count or grams
    count_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:large\s+)?(?:eggs?|slices?|pcs?|pieces?|cups?|bars?|tbsp|tsp)\b', food_name.lower())
    gram_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:g|gr|gram|grams)\b', food_name.lower())
    
    target_count = float(count_match.group(1)) if count_match else None
    target_grams = float(gram_match.group(1)) if gram_match else None

    # Clean query for search
    clean_query = re.sub(r'\(.*?\)', '', food_name)
    clean_query = re.sub(r'\b\d+\s*(?:large\s+)?(?:eggs?|slices?|pcs?|pieces?|cups?|bars?|g|gr|gram|grams|kg|oz|lbs?)\b', '', clean_query, flags=re.IGNORECASE).strip()
    if not clean_query:
        clean_query = food_name

    # 1. Open search page
    js_navigate = f"window.location.href = 'https://www.myfitnesspal.com/food/add_to_diary?meal={meal_idx}';"
    execute_cdp_in_tab(tab_id, js_navigate)
    time.sleep(1.8)

    # 2. Search food item
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

    # 3. Select match, inspect serving unit, calculate exact multiplier, and add
    js_select_and_add = f"""
    (() => {{
        // Find first search item
        const match = document.querySelector('ul#matching li a.search, a.search');
        if (match) {{
            match.click();
            setTimeout(() => {{
                const qtyInput = document.querySelector('input#food_entry_quantity, input[name*="quantity"]');
                const weightSelect = document.querySelector('select#food_entry_weight_id, select[name*="weight"]');
                const selectedText = weightSelect && weightSelect.selectedOptions.length > 0 ? weightSelect.selectedOptions[0].text.toLowerCase() : (match.parentElement ? match.parentElement.innerText.toLowerCase() : '');
                
                let qty = 1.0;
                const targetCount = {target_count if target_count is not None else 'null'};
                const targetGrams = {target_grams if target_grams is not None else 'null'};
                
                if (targetCount !== null) {{
                    // Check if unit is e.g. "3 whole egg" or "1 egg"
                    const unitCountMatch = selectedText.match(/(\\d+(?:\\.\\d+)?)\\s*(?:whole\\s+)?(?:eggs?|slices?|pcs?|pieces?|cups?|bars?)/);
                    if (unitCountMatch) {{
                        const baseCount = parseFloat(unitCountMatch[1]);
                        qty = targetCount / (baseCount > 0 ? baseCount : 1.0);
                    }} else {{
                        qty = targetCount;
                    }}
                }} else if (targetGrams !== null) {{
                    if (selectedText.includes('100 g') || selectedText.includes('100g') || selectedText.includes('100 gram')) {{
                        qty = targetGrams / 100.0;
                    }} else if (selectedText.includes('1 g') || selectedText.includes('1g') || selectedText.includes('1 gram')) {{
                        qty = targetGrams;
                    }} else {{
                        qty = targetGrams / 100.0;
                    }}
                }}

                if (qtyInput) {{
                    qtyInput.value = (Math.round(qty * 10) / 10).toString();
                }}
                
                const addBtn = document.querySelector('#add_button, input[value*="Add Food"], button[type="submit"]');
                if (addBtn) addBtn.click();
            }}, 1800);
        }}
    }})()
    """
    execute_cdp_in_tab(tab_id, js_select_and_add)
    time.sleep(3)

    execute_cdp_in_tab(tab_id, "window.location.href = 'https://www.myfitnesspal.com/food/diary';")
    time.sleep(2)

    return {"status": "succeeded", "message": f"Successfully added {food_name} to {meal_category} in MyFitnessPal"}
