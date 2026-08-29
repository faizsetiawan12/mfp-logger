from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional, List, Any

from mfp_logger.domain import FoodItem, MealCategory

class SubmissionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    DUPLICATE_DETECTED = "duplicate_detected"
    UNCERTAIN = "uncertain"
    FAILED = "failed"
    DRY_RUN = "dry_run"

@dataclass
class DiaryEntry:
    food_id: str
    diary_date: date
    meal_category: MealCategory
    weight_id: str
    quantity: float

@dataclass
class PreflightResult:
    is_duplicate: bool
    matching_entries: List[DiaryEntry]

@dataclass
class SubmissionResult:
    status: SubmissionStatus
    message: str
    entry: Optional[DiaryEntry] = None
    error: Optional[str] = None

class MyFitnessPalAdapter:
    def __init__(self, browser_context: Any = None, dry_run: bool = True):
        self.browser_context = browser_context
        self.dry_run = dry_run

    def check_duplicate(self, item: FoodItem, diary_date: date, meal_category: MealCategory) -> PreflightResult:
        if not self.browser_context:
            return PreflightResult(is_duplicate=False, matching_entries=[])
        
        entries = self.browser_context.get_diary_entries(diary_date, meal_category)
        matches = [e for e in entries if e.food_id == item.mfp_food_id]
        return PreflightResult(is_duplicate=len(matches) > 0, matching_entries=matches)

    def submit_item(self, item: FoodItem, diary_date: date, meal_category: MealCategory) -> SubmissionResult:
        if self.dry_run:
            return SubmissionResult(
                status=SubmissionStatus.DRY_RUN,
                message=f"[Dry Run] Prepared submission for {item.name} on {diary_date} ({meal_category.value})"
            )

        if not self.browser_context:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                message="Browser context required for live submissions."
            )

        food_id = item.mfp_food_id
        weight_id = item.mfp_weight_id or "1"

        # Create private custom food if missing or marked custom
        if not food_id or item.is_custom_food:
            custom_name = f"{item.name} [Estimate {diary_date.isoformat()}]"
            custom_entry = self.browser_context.create_custom_food(
                name=custom_name,
                calories=item.calories,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
            )
            food_id = custom_entry["food_id"]
            weight_id = custom_entry.get("weight_id", "1")

        # Submit single entry
        try:
            status_code = self.browser_context.add_diary_entry(
                food_id=food_id,
                diary_date=diary_date,
                meal_category=meal_category,
                weight_id=weight_id,
                quantity=item.quantity,
            )
        except TimeoutError as te:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Submission request timed out. Outcome uncertain; manual inspection required: {te}",
                error=str(te)
            )
        except Exception as ex:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                message=f"Submission failed with error: {ex}",
                error=str(ex)
            )

        # Post-submit verification: reload diary and verify exactly one matching entry
        entries = self.browser_context.get_diary_entries(diary_date, meal_category)
        matching = [e for e in entries if e.food_id == food_id and e.quantity == item.quantity]
        if len(matching) == 1:
            return SubmissionResult(
                status=SubmissionStatus.SUCCEEDED,
                message=f"Successfully submitted and verified exactly 1 matching entry for {item.name}.",
                entry=matching[0]
            )
        elif len(matching) > 1:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Warning: Multiple entries ({len(matching)}) found in diary for {item.name}.",
            )
        else:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Entry was accepted (HTTP {status_code}) but read-back verification found 0 matching entries.",
            )
