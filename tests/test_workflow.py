import pytest
from datetime import datetime, timezone, timedelta, date
import zoneinfo
from mfp_logger.domain import (
    MealInput,
    MealPreview,
    FoodItem,
    MealCategory,
    ConfidenceLevel,
    EvidenceSource,
    WorkflowStatus,
)
from mfp_logger.workflow import MealLoggingWorkflow

def test_low_confidence_meal_triggers_clarification_and_blocks_confirmation():
    workflow = MealLoggingWorkflow()
    # Simulating blurry image input or low confidence scenario
    meal_input = MealInput(
        text="A bowl of mystery soup with unknown ingredients",
        timestamp=datetime(2026, 8, 29, 12, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta")),
    )
    result = workflow.process_input(meal_input)
    assert result.status == WorkflowStatus.CLARIFICATION_NEEDED
    assert result.preview.confidence == ConfidenceLevel.LOW
    assert result.preview.clarification_prompt is not None

    # Attempting to confirm a low confidence meal must fail
    confirm_result = workflow.confirm(result.meal_id)
    assert confirm_result.status == WorkflowStatus.FAILED
    assert "Clarification required" in confirm_result.message

def test_relative_date_and_meal_overrides():
    workflow = MealLoggingWorkflow()
    # 2026-08-29 at 08:00 (normally breakfast today)
    # text says "yesterday's dinner: grilled salmon and asparagus"
    meal_input = MealInput(
        text="yesterday's dinner: grilled salmon and asparagus",
        timestamp=datetime(2026, 8, 29, 8, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta")),
    )
    result = workflow.process_input(meal_input)
    assert result.preview.diary_date == date(2026, 8, 28)
    assert result.preview.meal_category == MealCategory.DINNER

def test_confirmation_invalidation_on_correction_and_expiration():
    workflow = MealLoggingWorkflow()
    # 1. Expired meal confirmation (> 24 hours)
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    meal_input = MealInput(
        text="2 eggs",
        timestamp=old_time,
    )
    res = workflow.process_input(meal_input)
    confirm_res = workflow.confirm(res.meal_id)
    assert confirm_res.status == WorkflowStatus.FAILED
    assert "expired" in confirm_res.message.lower()

    # 2. Correction invalidates prior confirmation and creates fresh preview
    fresh_input = MealInput(text="2 eggs", timestamp=datetime.now(timezone.utc))
    fresh_res = workflow.process_input(fresh_input)
    confirm_ok = workflow.confirm(fresh_res.meal_id)
    assert confirm_ok.status == WorkflowStatus.CONFIRMED

    # Apply correction
    correction_res = workflow.correct(fresh_res.meal_id, {"quantity": 3})
    assert correction_res.status == WorkflowStatus.AWAITING_CONFIRMATION
    # Old approval was invalidated
    assert workflow.get_status(fresh_res.meal_id) == WorkflowStatus.AWAITING_CONFIRMATION

def test_cancellation_of_prepared_meal():
    workflow = MealLoggingWorkflow()
    meal_input = MealInput(text="2 eggs", timestamp=datetime.now(timezone.utc))
    res = workflow.process_input(meal_input)
    cancel_res = workflow.cancel(res.meal_id)
    assert cancel_res.status == WorkflowStatus.CANCELLED
    assert workflow.get_status(res.meal_id) == WorkflowStatus.CANCELLED
