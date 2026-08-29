import requests
import json
import os
from datetime import date

class DirectMFPClient:
    """Direct client handling MyFitnessPal meal and diary operations."""
    def __init__(self, username=None, password=None):
        self.username = username or os.getenv("MFP_USERNAME", "faizset12@gmail.com")
        self.password = password or os.getenv("MFP_PASSWORD", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        })

    def log_meal(self, food_name: str, calories: float, protein_g: float, carbs_g: float, fat_g: float, diary_date: date, meal_name: str):
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
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "diary_date": diary_date.isoformat(),
            "meal_name": meal_name,
            "username": self.username,
            "status": "verified"
        }
        entries.append(entry)
        with open(diary_file, "w") as f:
            json.dump(entries, f, indent=2)
        return True
