import subprocess
import json
import re

def execute_cdp_in_tab(tab_id: str, js_code: str) -> str:
    """Executes javascript inside an active Chrome tab via WebSocket and PowerShell."""
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
    # 1. Get tab id
    ps_tabs = "(Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/list' -UseBasicParsing).Content"
    tabs_res = subprocess.run([
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_tabs
    ], capture_output=True, text=True)
    
    tab_id = None
    try:
        tabs = json.loads(tabs_res.stdout.strip())
        for t in tabs:
            if "myfitnesspal.com/food/diary" in t.get("url", ""):
                tab_id = t.get("id")
                break
    except Exception:
        pass

    if not tab_id:
        return {"status": "error", "message": "MyFitnessPal food diary tab not found in Chrome"}

    # 2. Add quick calorie/macro entry directly into the MyFitnessPal page DOM
    meal_map = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
    meal_idx = meal_map.get(meal_category.lower(), 1)
    
    js_add = f"""
    (async () => {{
        try {{
            // Direct submission to MyFitnessPal diary
            const formData = new URLSearchParams();
            formData.append('utf8', '✓');
            formData.append('authenticity_token', typeof AUTH_TOKEN !== 'undefined' ? AUTH_TOKEN : '');
            formData.append('food_entry[date]', new Date().toISOString().split('T')[0]);
            formData.append('food_entry[meal_id]', '{meal_idx}');
            formData.append('food_entry[description]', '{food_name}');
            formData.append('food_entry[calories]', '{calories}');
            formData.append('food_entry[protein]', '{protein}');
            formData.append('food_entry[carbohydrates]', '{carbs}');
            formData.append('food_entry[fat]', '{fat}');

            const res = await fetch('https://www.myfitnesspal.com/food/add_quick_add', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Accept': 'text/javascript, application/javascript, */*'
                }},
                body: formData.toString()
            }});
            
            // Reload diary
            window.location.reload();
            return {{ status: 200, ok: true, message: 'Successfully added to MyFitnessPal diary' }};
        }} catch (e) {{
            return {{ error: e.toString() }};
        }}
    }})()
    """
    return execute_cdp_in_tab(tab_id, js_add)
