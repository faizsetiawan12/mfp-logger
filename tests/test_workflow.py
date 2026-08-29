import pytest
from datetime import datetime, timezone, timedelta, date
import zoneinfo
import tempfile
import os
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
from mfp_logger.mfp_adapter import MyFitnessPalAdapter, DiaryEntry
from mfp_logger.audit import AuditLogger
from mfp_logger.storage import ImageStorage
from test_mfp_adapter import MockBrowserContext

def test_low_confidence_meal_triggers_clarification_and_blocks_confirmation():
    workflow = MealLoggingWorkflow()
    meal_input = MealInput(
        text="A bowl of mystery soup with unknown ingredients",
        timestamp=datetime(2026, 8, 29, 12, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta")),
    )
    result = workflow.process_input(meal_input)
    assert result.status == WorkflowStatus.CLARIFICATION_NEEDED
    assert result.preview.confidence == ConfidenceLevel.LOW
    assert result.preview.clarification_prompt is not None

    confirm_result = workflow.confirm(result.meal_id)
    assert confirm_result.status == WorkflowStatus.FAILED
    assert "Clarification required" in confirm_result.message

def test_relative_date_and_meal_overrides():
    workflow = MealLoggingWorkflow()
    meal_input = MealInput(
        text="yesterday's dinner: grilled salmon and asparagus",
        timestamp=datetime(2026, 8, 29, 8, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta")),
    )
    result = workflow.process_input(meal_input)
    assert result.preview.diary_date == date(2026, 8, 28)
    assert result.preview.meal_category == MealCategory.DINNER

def test_confirmation_invalidation_on_correction_and_expiration():
    workflow = MealLoggingWorkflow()
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    meal_input = MealInput(
        text="2 eggs",
        timestamp=old_time,
    )
    res = workflow.process_input(meal_input)
    confirm_res = workflow.confirm(res.meal_id)
    assert confirm_res.status == WorkflowStatus.FAILED
    assert "expired" in confirm_res.message.lower()

    fresh_input = MealInput(text="2 eggs", timestamp=datetime.now(timezone.utc))
    fresh_res = workflow.process_input(fresh_input)
    confirm_ok = workflow.confirm(fresh_res.meal_id)
    assert confirm_ok.status == WorkflowStatus.SUCCEEDED

    correction_res = workflow.correct(fresh_res.meal_id, {"quantity": 3})
    assert correction_res.status == WorkflowStatus.AWAITING_CONFIRMATION
    assert workflow.get_status(fresh_res.meal_id) == WorkflowStatus.AWAITING_CONFIRMATION

def test_clarification_resolution_via_correction():
    workflow = MealLoggingWorkflow()
    meal_input = MealInput(text="mystery soup", timestamp=datetime.now(timezone.utc))
    res = workflow.process_input(meal_input)
    assert res.status == WorkflowStatus.CLARIFICATION_NEEDED

    # Correct with clarified details
    corrected = workflow.correct(res.meal_id, {"food_name": "Chicken Noodle Soup"})
    assert corrected.status == WorkflowStatus.AWAITING_CONFIRMATION
    assert corrected.preview.confidence == ConfidenceLevel.HIGH
    
    # Can now confirm
    confirm_res = workflow.confirm(res.meal_id)
    assert confirm_res.status in (WorkflowStatus.SUCCEEDED, WorkflowStatus.CONFIRMED)

def test_cancellation_of_prepared_meal():
    workflow = MealLoggingWorkflow()
    meal_input = MealInput(text="2 eggs", timestamp=datetime.now(timezone.utc))
    res = workflow.process_input(meal_input)
    cancel_res = workflow.cancel(res.meal_id)
    assert cancel_res.status == WorkflowStatus.CANCELLED
    assert workflow.get_status(res.meal_id) == WorkflowStatus.CANCELLED

def test_end_to_end_submission_and_image_cleanup():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "audit.jsonl")
        image_path = os.path.join(tmpdir, "meal.jpg")
        with open(image_path, "w") as f:
            f.write("photo")

        mock_browser = MockBrowserContext()
        adapter = MyFitnessPalAdapter(browser_context=mock_browser, dry_run=False)
        audit = AuditLogger(log_file=log_file)
        storage = ImageStorage(base_dir=tmpdir)
        
        workflow = MealLoggingWorkflow(
            adapter=adapter,
            audit_logger=audit,
            image_storage=storage,
        )

        meal_input = MealInput(
            text="2 hard boiled eggs",
            image_path=image_path,
            timestamp=datetime.now(timezone.utc),
            retain_recipe_photo=False,
        )
        res = workflow.process_input(meal_input)
        confirm_res = workflow.confirm(res.meal_id)
        
        assert confirm_res.status == WorkflowStatus.SUCCEEDED
        assert len(mock_browser.diary) == 1
        # Photo was cleaned up after successful verification
        assert not os.path.exists(image_path)
        # Audit log was written
        assert os.path.exists(log_file)
