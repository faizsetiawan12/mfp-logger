import uuid
import copy
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Optional, List, Any
import zoneinfo

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
from mfp_logger.mfp_adapter import (
    MyFitnessPalAdapter,
    DiarySubmissionPayload,
    SubmissionResult,
    SubmissionStatus,
)
from mfp_logger.audit import AuditLogger
from mfp_logger.storage import ImageStorage

class MealLoggingWorkflow:
    def __init__(
        self,
        time_zone_str: str = "Asia/Jakarta",
        estimator: Optional[NutritionEstimator] = None,
        adapter: Optional[MyFitnessPalAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
        image_storage: Optional[ImageStorage] = None,
    ):
        self.time_zone_str = time_zone_str
        self.estimator = estimator or NutritionEstimator()
        self.adapter = adapter or MyFitnessPalAdapter(dry_run=True)
        self.audit_logger = audit_logger or AuditLogger()
        self.image_storage = image_storage or ImageStorage()
        self._previews: Dict[str, MealPreview] = {}
        self._states: Dict[str, WorkflowStatus] = {}

    def get_status(self, meal_id: str) -> Optional[WorkflowStatus]:
        return self._states.get(meal_id)

    def _not_found_result(self, meal_id: str) -> WorkflowResult:
        return WorkflowResult(
            status=WorkflowStatus.FAILED,
            meal_id=meal_id,
            error="Meal not found"
        )

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
            user_id=meal_input.user_id,
            image_path=meal_input.image_path,
            retain_recipe_photo=meal_input.retain_recipe_photo,
        )
        
        self._previews[meal_id] = preview
        
        if confidence == ConfidenceLevel.LOW:
            self._states[meal_id] = WorkflowStatus.CLARIFICATION_NEEDED
            self.audit_logger.log({
                "action": "process_input",
                "meal_id": meal_id,
                "status": "clarification_needed",
                "confidence": confidence.value,
            })
            return WorkflowResult(
                status=WorkflowStatus.CLARIFICATION_NEEDED,
                meal_id=meal_id,
                preview=preview,
                message=clarification_prompt or "Clarification needed before confirmation."
            )
        
        self._states[meal_id] = WorkflowStatus.AWAITING_CONFIRMATION
        self.audit_logger.log({
            "action": "process_input",
            "meal_id": meal_id,
            "status": "awaiting_confirmation",
            "confidence": confidence.value,
        })
        return WorkflowResult(
            status=WorkflowStatus.AWAITING_CONFIRMATION,
            meal_id=meal_id,
            preview=preview,
            message="Meal prepared. Please confirm."
        )

    def confirm(self, meal_id: str) -> WorkflowResult:
        if meal_id not in self._previews:
            return self._not_found_result(meal_id)
        
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
        self.audit_logger.log({"action": "confirm_meal", "meal_id": meal_id, "status": "confirmed"})

        # End-to-end atomic submission through adapter
        self._states[meal_id] = WorkflowStatus.SUBMITTING
        submission_outcomes = []
        overall_status = WorkflowStatus.SUCCEEDED

        for item in preview.items:
            payload = DiarySubmissionPayload(
                food_id=item.mfp_food_id,
                name=item.name,
                diary_date=preview.diary_date,
                meal_category=preview.meal_category,
                weight_id=item.mfp_weight_id,
                quantity=item.quantity,
                is_custom_food=item.is_custom_food,
                calories=item.calories,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
            )
            res = self.adapter.submit_diary_entry(payload)
            submission_outcomes.append(res)
            if res.status == SubmissionStatus.UNCERTAIN:
                overall_status = WorkflowStatus.UNCERTAIN
            elif res.status in (SubmissionStatus.FAILED, SubmissionStatus.DUPLICATE_DETECTED):
                if overall_status != WorkflowStatus.UNCERTAIN:
                    overall_status = WorkflowStatus.FAILED if res.status == SubmissionStatus.FAILED else WorkflowStatus.PENDING

        self._states[meal_id] = overall_status
        self.audit_logger.log({
            "action": "execute_submission",
            "meal_id": meal_id,
            "status": overall_status.value,
            "items_count": len(preview.items),
        })

        # Cleanup image after successful verification
        if overall_status == WorkflowStatus.SUCCEEDED and preview.image_path:
            self.image_storage.cleanup_image(preview.image_path, retain_for_recipe=preview.retain_recipe_photo)

        return WorkflowResult(
            status=overall_status,
            meal_id=meal_id,
            preview=preview,
            message=f"Meal submission finished with status: {overall_status.value}",
            verification_details={"results": [r.message for r in submission_outcomes]}
        )

    def correct(self, meal_id: str, corrections: Dict[str, Any]) -> WorkflowResult:
        if meal_id not in self._previews:
            return self._not_found_result(meal_id)
        
        old_preview = self._previews[meal_id]
        new_items = copy.deepcopy(old_preview.items)
        new_confidence = old_preview.confidence
        clarification_prompt = None

        if "quantity" in corrections and new_items:
            for item in new_items:
                item.quantity = float(corrections["quantity"])

        if "food_name" in corrections and new_items:
            new_items[0].name = str(corrections["food_name"])
            # Clarifying food details upgrades confidence if resolved
            new_confidence = ConfidenceLevel.HIGH
            new_items[0].confidence = ConfidenceLevel.HIGH
            new_items[0].evidence_source = EvidenceSource.INGREDIENT_CALCULATION

        new_preview = MealPreview(
            meal_id=meal_id,
            diary_date=old_preview.diary_date,
            meal_category=old_preview.meal_category,
            items=new_items,
            confidence=new_confidence,
            created_at=datetime.now(timezone.utc),
            clarification_prompt=clarification_prompt,
            user_id=old_preview.user_id,
            image_path=old_preview.image_path,
            retain_recipe_photo=old_preview.retain_recipe_photo,
        )
        self._previews[meal_id] = new_preview
        self._states[meal_id] = WorkflowStatus.AWAITING_CONFIRMATION
        
        self.audit_logger.log({
            "action": "correct_meal",
            "meal_id": meal_id,
            "status": "awaiting_confirmation",
            "confidence": new_confidence.value,
        })
        
        return WorkflowResult(
            status=WorkflowStatus.AWAITING_CONFIRMATION,
            meal_id=meal_id,
            preview=new_preview,
            message="Meal updated with corrections. Prior confirmation invalidated. Please review and confirm."
        )

    def cancel(self, meal_id: str) -> WorkflowResult:
        if meal_id not in self._previews:
            return self._not_found_result(meal_id)
        self._states[meal_id] = WorkflowStatus.CANCELLED
        self.audit_logger.log({"action": "cancel_meal", "meal_id": meal_id, "status": "cancelled"})
        return WorkflowResult(
            status=WorkflowStatus.CANCELLED,
            meal_id=meal_id,
            preview=self._previews[meal_id],
            message="Meal logging cancelled."
        )
