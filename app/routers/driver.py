import secrets
import string
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.team_member import TeamMember, TeamMemberRole
from app.schemas.team_member import TeamMemberResponse
from app.core.logging_config import logger

router = APIRouter()

class ActivationCodeResponse(BaseModel):
    activation_code: str


def generate_activation_code() -> str:
    """Generate a secure, 12-digit numeric-only activation key."""
    return "".join(secrets.choice(string.digits) for _ in range(12))


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
    
    # Query for the team member
    driver = db.query(TeamMember).filter(
        TeamMember.id == driver_id,
        TeamMember.role_type == TeamMemberRole.driver
    ).first()
    
    if not driver:
        logger.warning(f"Driver with ID {driver_id} not found or is not a driver")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
        
    # Generate and assign activation code
    activation_code = generate_activation_code()
    
    # Check uniqueness (extremely rare collision but good practice)
    collision_check = db.query(TeamMember).filter(TeamMember.activation_code == activation_code).first()
    attempts = 0
    while collision_check and attempts < 10:
        activation_code = generate_activation_code()
        collision_check = db.query(TeamMember).filter(TeamMember.activation_code == activation_code).first()
        attempts += 1
        
    driver.activation_code = activation_code
    db.commit()
    db.refresh(driver)
    
    logger.info(f"Successfully activated driver ID {driver_id} with code: {activation_code}")
    return {"activation_code": activation_code}


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
        
    # Query for the driver using the activation code
    driver = db.query(TeamMember).filter(
        TeamMember.activation_code == code,
        TeamMember.role_type == TeamMemberRole.driver
    ).first()
    
    if not driver:
        logger.warning("Verification attempt failed: invalid activation code")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid activation code or driver not found"
        )
        
    logger.info(f"Driver verified successfully: ID {driver.id}, name={driver.name}")
    return driver
