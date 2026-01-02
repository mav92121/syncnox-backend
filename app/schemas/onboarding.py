from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Industry(str, Enum):
    E_COMMERCE = "e_commerce"
    LOGISTICS_FREIGHT = "logistics_freight"
    FIELD_SERVICE = "field_service"
    FOOD_GROCERY = "food_grocery"
    COURIER_EXPRESS = "courier_express"
    MEDICAL_PHARMACY = "medical_pharmacy"
    CONSTRUCTION = "construction"
    OTHER = "other"


class OnboardingResponse(BaseModel):
    """Response schema for onboarding status"""
    tenant_id: int
    is_completed: bool
    current_step: int
    company_name: Optional[str] = None
    industry: Optional[str] = None

    class Config:
        from_attributes = True


class BasicInfoRequest(BaseModel):
    """Request schema for saving basic info (step 1)"""
    company_name: str
    industry: Industry


class AdvanceStepRequest(BaseModel):
    """Request schema for advancing to next step"""
    step: int  # The step to advance to (1-4)
