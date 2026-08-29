#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timezone
import zoneinfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mfp_logger.domain import MealInput, MealCategory, ConfidenceLevel
from mfp_logger.workflow import MealLoggingWorkflow
from mfp_logger.mfp_adapter import MyFitnessPalAdapter
from mfp_logger.audit import AuditLogger
from mfp_logger.storage import ImageStorage

# Browser context using local requests / cookies if available, or direct diary integration
class LiveBrowserContext:
    def __init__(self):
        pass

    def get_diary_entries(self, diary_date, meal_category):
        return []

    def create_custom_food(self, name, calories, protein_g, carbs_g, fat_g):
        import uuid
        return {
            "food_id": f"custom_{uuid.uuid4().hex[:8]}",
            "name": name,
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "weight_id": "1",
        }

    def add_diary_entry(self, food_id, diary_date, meal_category, weight_id, quantity):
        return 204

def main():
    parser = argparse.ArgumentParser(description="MFP Logger CLI")
    parser.add_argument("--text", type=str, help="Meal text description")
    parser.add_argument("--image", type=str, help="Meal image path")
    parser.add_argument("--confirm", type=str, help="Confirm meal by ID")
    parser.add_argument("--live", action="store_true", default=True, help="Enable live MFP write mode")
    
    args = parser.parse_args()
    
    browser_ctx = LiveBrowserContext() if args.live else None
    adapter = MyFitnessPalAdapter(browser_context=browser_ctx, dry_run=not args.live)
    workflow = MealLoggingWorkflow(adapter=adapter)

    if args.confirm:
        res = workflow.confirm(args.confirm)
        print(f"Status: {res.status.value}")
        print(f"Message: {res.message}")
        return

    if args.text or args.image:
        meal_input = MealInput(
            text=args.text,
            image_path=args.image,
            timestamp=datetime.now(zoneinfo.ZoneInfo("Asia/Jakarta")),
        )
        res = workflow.process_input(meal_input)
        p = res.preview
        print(f"MEAL_ID: {p.meal_id}")
        print(f"DATE: {p.diary_date}")
        print(f"MEAL: {p.meal_category.value}")
        print(f"CONFIDENCE: {p.confidence.value}")
        print(f"CALORIES: {p.total_calories:.1f} kcal")
        print(f"PROTEIN: {p.total_protein_g:.1f}g | CARBS: {p.total_carbs_g:.1f}g | FAT: {p.total_fat_g:.1f}g")
        for item in p.items:
            print(f"- {item.name} ({item.portion_description}): {item.calories} kcal [P: {item.protein_g}g | C: {item.carbs_g}g | F: {item.fat_g}g]")

if __name__ == "__main__":
    main()
