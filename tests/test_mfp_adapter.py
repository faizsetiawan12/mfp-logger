import pytest
from datetime import date
from mfp_logger.domain import (
    MealPreview,
    FoodItem,
    MealCategory,
    ConfidenceLevel,
    EvidenceSource,
    WorkflowStatus,
)
from mfp_logger.mfp_adapter import (
    MyFitnessPalAdapter,
    DiaryEntry,
    SubmissionResult,
    SubmissionStatus,
)

class MockBrowserContext:
    def __init__(self):
        self.diary: list[DiaryEntry] = []
        self.custom_foods: list[dict] = []
        self.fail_network: bool = False
        self.timeout_network: bool = False

    def search_food(self, query: str) -> list[dict]:
        if "oatmeal" in query.lower():
            return [{"food_id": "12345", "name": "Rolled Oats", "weight_id": "99", "serving_unit": "1 cup"}]
        return []

    def create_custom_food(self, name: str, calories: float, protein_g: float, carbs_g: float, fat_g: float) -> dict:
        food_id = f"custom_{len(self.custom_foods) + 1}"
        entry = {
            "food_id": food_id,
            "name": name,
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "weight_id": "1",
        }
        self.custom_foods.append(entry)
        return entry

    def get_diary_entries(self, diary_date: date, meal_category: MealCategory) -> list[DiaryEntry]:
        return [e for e in self.diary if e.diary_date == diary_date and e.meal_category == meal_category]

    def add_diary_entry(self, food_id: str, diary_date: date, meal_category: MealCategory, weight_id: str, quantity: float) -> int:
        if self.fail_network:
            raise RuntimeError("Network error")
        if self.timeout_network:
            raise TimeoutError("Request timed out")
        entry = DiaryEntry(
            food_id=food_id,
            diary_date=diary_date,
            meal_category=meal_category,
            weight_id=weight_id,
            quantity=quantity,
        )
        self.diary.append(entry)
        return 204

def test_missing_food_creates_private_custom_food_and_submits():
    mock_browser = MockBrowserContext()
    adapter = MyFitnessPalAdapter(browser_context=mock_browser, dry_run=False)
    
    item = FoodItem(
        name="Homemade Soto Ayam",
        portion_description="1 bowl",
        calories=350.0,
        protein_g=25.0,
        carbs_g=30.0,
        fat_g=12.0,
        evidence_source=EvidenceSource.VISION_ESTIMATE,
        is_custom_food=True,
    )
    
    res = adapter.submit_item(item, diary_date=date(2026, 8, 29), meal_category=MealCategory.LUNCH)
    
    assert res.status == SubmissionStatus.SUCCEEDED
    assert len(mock_browser.custom_foods) == 1
    # Custom food name contains estimate label and date
    assert "[Estimate 2026-08-29]" in mock_browser.custom_foods[0]["name"]
    # Verified exactly 1 matching entry in diary
    assert len(mock_browser.diary) == 1

def test_duplicate_preflight_detects_existing_entry():
    mock_browser = MockBrowserContext()
    # Pre-populate diary
    mock_browser.diary.append(DiaryEntry(
        food_id="12345",
        diary_date=date(2026, 8, 29),
        meal_category=MealCategory.BREAKFAST,
        weight_id="99",
        quantity=1.0,
    ))
    
    adapter = MyFitnessPalAdapter(browser_context=mock_browser, dry_run=False)
    item = FoodItem(
        name="Rolled Oats",
        portion_description="1 cup",
        calories=150.0,
        protein_g=5.0,
        carbs_g=27.0,
        fat_g=3.0,
        mfp_food_id="12345",
        mfp_weight_id="99",
        quantity=1.0,
    )
    
    preflight = adapter.check_duplicate(item, diary_date=date(2026, 8, 29), meal_category=MealCategory.BREAKFAST)
    assert preflight.is_duplicate is True

def test_timeout_marks_submission_as_uncertain_never_blindly_retried():
    mock_browser = MockBrowserContext()
    mock_browser.timeout_network = True
    adapter = MyFitnessPalAdapter(browser_context=mock_browser, dry_run=False)
    
    item = FoodItem(
        name="Rolled Oats",
        portion_description="1 cup",
        calories=150.0,
        protein_g=5.0,
        carbs_g=27.0,
        fat_g=3.0,
        mfp_food_id="12345",
        mfp_weight_id="99",
        quantity=1.0,
    )
    
    res = adapter.submit_item(item, diary_date=date(2026, 8, 29), meal_category=MealCategory.BREAKFAST)
    assert res.status == SubmissionStatus.UNCERTAIN
