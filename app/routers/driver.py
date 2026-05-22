from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.schemas.team_member import TeamMemberResponse
from app.services.team_member import team_member_service
from app.core.logging_config import logger

router = APIRouter()

class ActivationCodeResponse(BaseModel):
    activation_code: str


@router.post("/{driver_id}/activate", response_model=ActivationCodeResponse, status_code=status.HTTP_200_OK)
def activate_driver(
    driver_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate and assign a unique 12-digit numeric activation code for a driver.
    
    Args:
        driver_id: ID of the team member (must have role_type='driver')
        db: Database session
        
    Returns:
        The generated activation code
    """
    logger.info(f"Activating driver with ID: {driver_id}")
    activation_code = team_member_service.activate_driver(db=db, driver_id=driver_id)
    return {"activation_code": activation_code}


@router.post("/{driver_id}/deactivate", status_code=status.HTTP_200_OK)
def deactivate_driver(
    driver_id: int,
    db: Session = Depends(get_db)
):
    """
    Deactivate a driver's mobile app by clearing their activation code.
    
    Args:
        driver_id: ID of the team member (must have role_type='driver')
        db: Database session
    """
    logger.info(f"Deactivating driver with ID: {driver_id}")
    team_member_service.deactivate_driver(db=db, driver_id=driver_id)
    return {"status": "success"}


@router.post("/verify", response_model=TeamMemberResponse, status_code=status.HTTP_200_OK)
def verify_driver(
    activation_code: Optional[str] = Header(None, alias="activation-code"),
    x_activation_code: Optional[str] = Header(None, alias="x-activation-code"),
    db: Session = Depends(get_db)
):
    """
    Verify the driver activation code and return the driver's info.
    Requires the activation code in the 'activation-code' header.
    
    Args:
        activation_code: The activation code passed via 'activation-code' header
        x_activation_code: Alternative 'x-activation-code' header
        db: Database session
        
    Returns:
        The driver team member's info
    """
    code = activation_code or x_activation_code
    
    if not code:
        logger.warning("Verification attempt failed: missing activation-code header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation code is required in the headers ('activation-code')"
        )
        
    driver = team_member_service.verify_driver(db=db, activation_code=code)
    logger.info(f"Driver verified successfully: ID {driver.id}, name={driver.name}")
    return driver
