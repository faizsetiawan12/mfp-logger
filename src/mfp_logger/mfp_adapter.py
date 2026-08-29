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
class DiarySubmissionPayload:
    food_id: Optional[str]
    name: str
    diary_date: date
    meal_category: MealCategory
    weight_id: Optional[str]
    quantity: float
    is_custom_food: bool
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float

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

    def check_duplicate(self, payload: DiarySubmissionPayload) -> PreflightResult:
        if not self.browser_context:
            return PreflightResult(is_duplicate=False, matching_entries=[])
        
        entries = self.browser_context.get_diary_entries(payload.diary_date, payload.meal_category)
        if payload.food_id:
            matches = [e for e in entries if e.food_id == payload.food_id and e.quantity == payload.quantity]
        else:
            # Check by custom food naming pattern if food_id is not yet assigned
            custom_pattern = f"{payload.name} [Estimate {payload.diary_date.isoformat()}]"
            matches = [
                e for e in entries 
                if getattr(e, "food_name", None) == custom_pattern and e.quantity == payload.quantity
            ]
        return PreflightResult(is_duplicate=len(matches) > 0, matching_entries=matches)

    def submit_diary_entry(self, payload: DiarySubmissionPayload) -> SubmissionResult:
        if self.dry_run:
            return SubmissionResult(
                status=SubmissionStatus.DRY_RUN,
                message=f"[Dry Run] Prepared submission for {payload.name} on {payload.diary_date} ({payload.meal_category.value})"
            )

        if not self.browser_context:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                message="Browser context required for live submissions."
            )

        # 1. Duplicate preflight check
        preflight = self.check_duplicate(payload)
        if preflight.is_duplicate:
            return SubmissionResult(
                status=SubmissionStatus.DUPLICATE_DETECTED,
                message=f"Duplicate entry detected in diary for {payload.name} on {payload.diary_date}."
            )

        food_id = payload.food_id
        weight_id = payload.weight_id or "1"

        # 2. Create private custom food if missing or marked custom (without existing food_id)
        if not food_id or (payload.is_custom_food and not payload.food_id):
            custom_name = f"{payload.name} [Estimate {payload.diary_date.isoformat()}]"
            custom_entry = self.browser_context.create_custom_food(
                name=custom_name,
                calories=payload.calories,
                protein_g=payload.protein_g,
                carbs_g=payload.carbs_g,
                fat_g=payload.fat_g,
            )
            food_id = custom_entry["food_id"]
            weight_id = custom_entry.get("weight_id", "1")

        # 3. Submit single entry
        try:
            status_code = self.browser_context.add_diary_entry(
                food_id=food_id,
                diary_date=payload.diary_date,
                meal_category=payload.meal_category,
                weight_id=weight_id,
                quantity=payload.quantity,
            )
        except TimeoutError as te:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Submission request timed out. Outcome uncertain; manual inspection required before retry: {te}",
                error=str(te)
            )
        except Exception as ex:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                message=f"Submission failed with error: {ex}",
                error=str(ex)
            )

        # 4. Post-submit verification: reload diary and verify exactly one matching entry
        entries = self.browser_context.get_diary_entries(payload.diary_date, payload.meal_category)
        matching = [
            e for e in entries 
            if e.food_id == food_id and e.quantity == payload.quantity and e.weight_id == weight_id
        ]
        if len(matching) == 1:
            return SubmissionResult(
                status=SubmissionStatus.SUCCEEDED,
                message=f"Successfully submitted and verified exactly 1 matching entry for {payload.name}.",
                entry=matching[0]
            )
        elif len(matching) > 1:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Warning: Multiple entries ({len(matching)}) found in diary for {payload.name}.",
            )
        else:
            return SubmissionResult(
                status=SubmissionStatus.UNCERTAIN,
                message=f"Entry was accepted (HTTP {status_code}) but read-back verification found 0 matching entries.",
            )
