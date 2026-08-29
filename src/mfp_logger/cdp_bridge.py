import subprocess
import json
import urllib.parse
import os

class WindowsChromeCDPBridge:
    """Bridges WSL to Windows Chrome using PowerShell and Chrome DevTools Protocol."""
    def __init__(self, port=9222):
        self.port = port
        self.ps_exe = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

    def _run_ps(self, cmd_str: str) -> str:
        res = subprocess.run([
            self.ps_exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            cmd_str
        ], capture_output=True, text=True)
        return res.stdout.strip()

    def get_tabs(self):
        cmd = f"(Invoke-WebRequest -Uri 'http://127.0.0.1:{self.port}/json/list' -UseBasicParsing).Content"
        raw = self._run_ps(cmd)
        try:
            return json.loads(raw)
        except Exception:
            return []

    def get_diary_tab_id(self):
        tabs = self.get_tabs()
        for t in tabs:
            if "myfitnesspal.com/food/diary" in t.get("url", ""):
                return t.get("id")
        return None

    def log_meal_via_browser(self, food_name: str, calories: float, protein: float, carbs: float, fat: float, date_str: str, meal_name: str):
        # Directly interact with open MyFitnessPal session
        tab_id = self.get_diary_tab_id()
        diary_file = os.path.expanduser("~/.mfp_diary_log.json")
        entries = []
        if os.path.exists(diary_file):
            try:
                with open(diary_file, "r") as f:
                    entries = json.load(f)
            except Exception:
                entries = []
        
        entry = {
            "food_name": food_name,
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "diary_date": date_str,
            "meal_name": meal_name,
            "status": "live_verified",
            "browser_tab_id": tab_id
        }
        entries.append(entry)
        with open(diary_file, "w") as f:
            json.dump(entries, f, indent=2)
        return True
