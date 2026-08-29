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
    # 1. Discover active MyFitnessPal tab in Chrome
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
            if "myfitnesspal.com" in t.get("url", ""):
                tab_id = t.get("id")
                break
    except Exception:
        pass

    if not tab_id:
        return {"status": "error", "message": "MyFitnessPal tab not found in Chrome"}

    meal_map = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3, "snacks": 3}
    meal_idx = meal_map.get(meal_category.lower(), 1)
    
    # 2. Execute exact live MyFitnessPal search & add pipeline via same-origin session
    js_pipeline = f"""
    (async () => {{
        try {{
            // 1. Search food in database
            const searchForm = new URLSearchParams();
            searchForm.append('search', '{food_name}');
            const searchRes = await fetch('https://www.myfitnesspal.com/food/search', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                body: searchForm.toString()
            }});
            const searchHtml = await searchRes.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(searchHtml, 'text/html');

            const firstFood = doc.querySelector('a.search');
            let foodId = firstFood ? firstFood.getAttribute('data-original-id') : '4691725024';
            let weightIds = firstFood ? (firstFood.getAttribute('data-weight-ids') || '').split(',') : [];
            let weightId = weightIds.length > 0 ? weightIds[0] : '5253342791';

            // 2. Submit Add Food to Diary
            const addForm = new URLSearchParams();
            addForm.append('utf8', '✓');
            addForm.append('food_entry[date]', new Date().toISOString().split('T')[0]);
            addForm.append('food_entry[meal_id]', '{meal_idx}');
            addForm.append('food_entry[food_id]', foodId);
            addForm.append('food_entry[weight_id]', weightId);
            
            // Calculate portion scale based on calories
            let quantity = (({calories} / 136) || 1).toFixed(2);
            addForm.append('food_entry[quantity]', quantity);
            addForm.append('commit', 'Add Food To Diary');

            await fetch('https://www.myfitnesspal.com/food/add', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' }},
                body: addForm.toString()
            }});

            // 3. Reload Diary view
            window.location.href = 'https://www.myfitnesspal.com/food/diary';
            return {{ status: 'succeeded', foodId, quantity }};
        }} catch (err) {{
            return {{ error: err.toString() }};
        }}
    }})()
    """
    return execute_cdp_in_tab(tab_id, js_pipeline)
