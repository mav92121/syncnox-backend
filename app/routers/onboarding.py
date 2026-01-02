from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.onboarding import (
    OnboardingResponse, 
    BasicInfoRequest, 
    AdvanceStepRequest
)
from app.crud.onboarding import onboarding as onboarding_crud
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger

router = APIRouter()


@router.get("", response_model=OnboardingResponse)
def get_onboarding_status(
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Get current onboarding status for the tenant.
    Creates a new onboarding record if one doesn't exist.
    """
    return onboarding_crud.get_by_tenant_id(db, _tenant_id)


@router.post("/basic-info", response_model=OnboardingResponse)
def save_basic_info(
    data: BasicInfoRequest,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Save basic info (company name and industry) and advance to step 2.
    """
    logger.info(f"Saving basic info for tenant {_tenant_id}: {data.company_name}")
    return onboarding_crud.update_basic_info(db, _tenant_id, data)


@router.post("/advance-step", response_model=OnboardingResponse)
def advance_step(
    data: AdvanceStepRequest,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Advance to a specific step.
    """
    logger.info(f"Advancing tenant {_tenant_id} to step {data.step}")
    return onboarding_crud.advance_step(db, _tenant_id, data.step)


@router.post("/complete", response_model=OnboardingResponse)
def complete_onboarding(
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Mark onboarding as completed.
    """
    logger.info(f"Completing onboarding for tenant {_tenant_id}")
    return onboarding_crud.complete_onboarding(db, _tenant_id)
