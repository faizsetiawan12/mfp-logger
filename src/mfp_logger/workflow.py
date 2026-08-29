import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Optional, List, Any
import zoneinfo
import copy

from mfp_logger.domain import (
    MealInput,
    MealPreview,
    FoodItem,
    MealCategory,
    ConfidenceLevel,
    EvidenceSource,
    WorkflowStatus,
    WorkflowResult,
)
from mfp_logger.estimator import NutritionEstimator

class MealLoggingWorkflow:
    def __init__(self, time_zone_str: str = "Asia/Jakarta", estimator: Optional[NutritionEstimator] = None):
        self.time_zone_str = time_zone_str
        self.estimator = estimator or NutritionEstimator()
        self._previews: Dict[str, MealPreview] = {}
        self._states: Dict[str, WorkflowStatus] = {}

    def get_status(self, meal_id: str) -> Optional[WorkflowStatus]:
        return self._states.get(meal_id)

    def _infer_meal_category_and_date(self, dt: datetime, text: Optional[str] = None) -> tuple[MealCategory, date]:
        tz = zoneinfo.ZoneInfo(self.time_zone_str)
        local_dt = dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=timezone.utc).astimezone(tz)
        target_date = local_dt.date()
        
        category = MealCategory.SNACK
        hour = local_dt.hour
        if 5 <= hour < 11:
            category = MealCategory.BREAKFAST
        elif 11 <= hour < 16:
            category = MealCategory.LUNCH
        elif 16 <= hour < 22:
            category = MealCategory.DINNER

        if text:
            lower = text.lower()
            if "yesterday" in lower:
                target_date = target_date - timedelta(days=1)
            if "breakfast" in lower:
                category = MealCategory.BREAKFAST
            elif "lunch" in lower:
                category = MealCategory.LUNCH
            elif "dinner" in lower:
                category = MealCategory.DINNER
            elif "snack" in lower:
                category = MealCategory.SNACK

        return category, target_date

    def process_input(self, meal_input: MealInput) -> WorkflowResult:
        dt = meal_input.timestamp or datetime.now(timezone.utc)
        category, target_date = self._infer_meal_category_and_date(dt, meal_input.text)
        
        items, confidence, clarification_prompt = self.estimator.estimate(meal_input)
        meal_id = str(uuid.uuid4())

        preview = MealPreview(
            meal_id=meal_id,
            diary_date=target_date,
            meal_category=category,
            items=items,
            confidence=confidence,
            created_at=dt,
            clarification_prompt=clarification_prompt,
        )
        
        self._previews[meal_id] = preview
        
        if confidence == ConfidenceLevel.LOW:
            self._states[meal_id] = WorkflowStatus.CLARIFICATION_NEEDED
            return WorkflowResult(
                status=WorkflowStatus.CLARIFICATION_NEEDED,
                meal_id=meal_id,
                preview=preview,
                message=clarification_prompt or "Clarification needed before confirmation."
            )
        
        self._states[meal_id] = WorkflowStatus.AWAITING_CONFIRMATION
        return WorkflowResult(
            status=WorkflowStatus.AWAITING_CONFIRMATION,
            meal_id=meal_id,
            preview=preview,
            message="Meal prepared. Please confirm."
        )

    def confirm(self, meal_id: str) -> WorkflowResult:
        if meal_id not in self._previews:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                meal_id=meal_id,
                error="Meal not found"
            )
        
        preview = self._previews[meal_id]
        current_state = self._states.get(meal_id)
        
        if preview.confidence == ConfidenceLevel.LOW or current_state == WorkflowStatus.CLARIFICATION_NEEDED:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                meal_id=meal_id,
                preview=preview,
                message="Clarification required. Cannot confirm low confidence meal."
            )
            
        now = datetime.now(timezone.utc)
        created_at_utc = preview.created_at.astimezone(timezone.utc) if preview.created_at.tzinfo else preview.created_at.replace(tzinfo=timezone.utc)
        if now - created_at_utc > timedelta(hours=24):
            self._states[meal_id] = WorkflowStatus.FAILED
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                meal_id=meal_id,
                preview=preview,
                message="Confirmation expired after 24 hours."
            )

        self._states[meal_id] = WorkflowStatus.CONFIRMED
        return WorkflowResult(
            status=WorkflowStatus.CONFIRMED,
            meal_id=meal_id,
            preview=preview,
            message="Meal confirmed successfully."
        )

    def correct(self, meal_id: str, corrections: Dict[str, Any]) -> WorkflowResult:
        if meal_id not in self._previews:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                meal_id=meal_id,
                error="Meal not found"
            )
        
        # Invalidate prior confirmation and generate updated preview
        old_preview = self._previews[meal_id]
        new_items = copy.deepcopy(old_preview.items)
        
        if "quantity" in corrections and new_items:
            for item in new_items:
                item.quantity = float(corrections["quantity"])

        new_preview = MealPreview(
            meal_id=meal_id,
            diary_date=old_preview.diary_date,
            meal_category=old_preview.meal_category,
            items=new_items,
            confidence=old_preview.confidence,
            created_at=datetime.now(timezone.utc),
        )
        self._previews[meal_id] = new_preview
        self._states[meal_id] = WorkflowStatus.AWAITING_CONFIRMATION
        
        return WorkflowResult(
            status=WorkflowStatus.AWAITING_CONFIRMATION,
            meal_id=meal_id,
            preview=new_preview,
            message="Meal updated with corrections. Prior confirmation invalidated. Please review and confirm."
        )

    def cancel(self, meal_id: str) -> WorkflowResult:
        if meal_id not in self._previews:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                meal_id=meal_id,
                error="Meal not found"
            )
        self._states[meal_id] = WorkflowStatus.CANCELLED
        return WorkflowResult(
            status=WorkflowStatus.CANCELLED,
            meal_id=meal_id,
            preview=self._previews[meal_id],
            message="Meal logging cancelled."
        )
