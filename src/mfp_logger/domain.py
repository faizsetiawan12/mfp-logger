from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class MealCategory(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class EvidenceSource(str, Enum):
    NUTRITION_LABEL = "nutrition_label"
    VERIFIED_RESTAURANT = "verified_restaurant"
    CONFIRMED_PERSONAL_RECIPE = "confirmed_personal_recipe"
    MFP_MATCH = "mfp_match"
    INGREDIENT_CALCULATION = "ingredient_calculation"
    VISION_ESTIMATE = "vision_estimate"

class WorkflowStatus(str, Enum):
    PREPARED = "prepared"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CLARIFICATION_NEEDED = "clarification_needed"
    CONFIRMED = "confirmed"
    SUBMITTING = "submitting"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"

@dataclass
class MealInput:
    text: Optional[str] = None
    image_path: Optional[str] = None
    timestamp: Optional[datetime] = None
    user_id: str = "default_user"
    timezone_name: str = "Asia/Jakarta"
    retain_recipe_photo: bool = False

@dataclass
class FoodItem:
    name: str
    portion_description: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    evidence_source: EvidenceSource = EvidenceSource.VISION_ESTIMATE
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    calorie_range_min: Optional[float] = None
    calorie_range_max: Optional[float] = None
    is_custom_food: bool = False
    mfp_food_id: Optional[str] = None
    mfp_weight_id: Optional[str] = None
    quantity: float = 1.0

@dataclass
class MealPreview:
    meal_id: str
    diary_date: date
    meal_category: MealCategory
    items: List[FoodItem]
    confidence: ConfidenceLevel
    created_at: datetime
    clarification_prompt: Optional[str] = None
    user_id: str = "default_user"
    image_path: Optional[str] = None
    retain_recipe_photo: bool = False

    @property
    def preview_expiration(self) -> datetime:
        return self.created_at + timedelta(hours=24)

    @property
    def total_calories(self) -> float:
        return sum(item.calories * item.quantity for item in self.items)

    @property
    def total_protein_g(self) -> float:
        return sum(item.protein_g * item.quantity for item in self.items)

    @property
    def total_carbs_g(self) -> float:
        return sum(item.carbs_g * item.quantity for item in self.items)

    @property
    def total_fat_g(self) -> float:
        return sum(item.fat_g * item.quantity for item in self.items)

@dataclass
class WorkflowResult:
    status: WorkflowStatus
    meal_id: Optional[str] = None
    preview: Optional[MealPreview] = None
    message: str = ""
    error: Optional[str] = None
    verification_details: Optional[Dict[str, Any]] = None
