#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timezone
import zoneinfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mfp_logger.domain import MealInput, MealCategory, ConfidenceLevel
from mfp_logger.workflow import MealLoggingWorkflow
from mfp_logger.direct_mfp import DirectMFPClient

def main():
    parser = argparse.ArgumentParser(description="MFP Logger CLI")
    parser.add_argument("--text", type=str, help="Meal text description")
    parser.add_argument("--image", type=str, help="Meal image path")
    parser.add_argument("--confirm", type=str, help="Confirm meal by text/id")
    parser.add_argument("--food", type=str, help="Food name")
    parser.add_argument("--calories", type=float, default=0.0, help="Calories")
    parser.add_argument("--protein", type=float, default=0.0, help="Protein (g)")
    parser.add_argument("--carbs", type=float, default=0.0, help="Carbs (g)")
    parser.add_argument("--fat", type=float, default=0.0, help="Fat (g)")
    parser.add_argument("--meal", type=str, default="lunch", help="Meal category")
    
    args = parser.parse_args()

    client = DirectMFPClient()

    if args.confirm and args.food:
        now_date = datetime.now(zoneinfo.ZoneInfo("Asia/Jakarta")).date()
        client.log_meal(
            food_name=args.food,
            calories=args.calories,
            protein_g=args.protein,
            carbs_g=args.carbs,
            fat_g=args.fat,
            diary_date=now_date,
            meal_name=args.meal
        )
        print("Status: succeeded")
        print(f"Message: Logged {args.food} ({args.calories} kcal) to MyFitnessPal diary for {now_date} ({args.meal}).")
        return

    if args.text or args.image:
        workflow = MealLoggingWorkflow()
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
