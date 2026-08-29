import pytest
from datetime import datetime, timezone
import zoneinfo
from mfp_logger.domain import MealInput, MealCategory, ConfidenceLevel, WorkflowStatus
from mfp_logger.workflow import MealLoggingWorkflow

def test_text_meal_input_creates_itemized_preview():
    workflow = MealLoggingWorkflow()
    # 8:30 AM local time Asia/Jakarta is 01:30 UTC
    meal_input = MealInput(
        text="2 hard boiled eggs and 1 slice whole wheat toast",
        timestamp=datetime(2026, 8, 29, 8, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Jakarta")),
    )
    
    result = workflow.process_input(meal_input)
    
    assert result.status == WorkflowStatus.AWAITING_CONFIRMATION
    assert result.preview is not None
    assert result.preview.meal_category == MealCategory.BREAKFAST
    assert len(result.preview.items) == 2
    assert result.preview.total_calories > 0
    assert result.preview.total_protein_g > 0
    assert result.preview.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
