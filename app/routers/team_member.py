from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.team_member import TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse
from app.services import team_member_service
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger

router = APIRouter()


@router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
def create_team_member(
    team_member_data: TeamMemberCreate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Create a new team member.
    
    The tenant is automatically identified from the JWT token.
    No need to provide tenant_id - it's completely transparent!
    
    Args:
        team_member_data: Team member creation data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT, used internally)
    
    Returns:
        Created team member
        
    Raises:
        HTTPException 400: If email already exists for this tenant
    """
    try:
        logger.info(f"Creating team member: name={team_member_data.name}, tenant_id={_tenant_id}")
        result = team_member_service.create_team_member(
            db=db,
            team_member_data=team_member_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Team member created successfully: id={result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating team member: {type(e).__name__}: {str(e)}")
        raise


@router.get("", response_model=List[TeamMemberResponse])
def get_team_members(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve all team members for your tenant.
    
    The tenant is automatically identified from the JWT token.
    Only returns team members belonging to your tenant.
    
    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT, used internally)
    
    Returns:
        List of team members belonging to your tenant
    """
    return team_member_service.get_team_members(
        db=db,
        tenant_id=_tenant_id,
        skip=skip,
        limit=limit
    )


@router.get("/{team_member_id}", response_model=TeamMemberResponse)
def get_team_member(
    team_member_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve a specific team member by ID.
    
    The tenant is automatically identified from the JWT token.
    Returns 404 if the team member doesn't exist or doesn't belong to your tenant.
    
    Args:
        team_member_id: ID of the team member to retrieve
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT, used internally)
    
    Returns:
        Team member details
    
    Raises:
        HTTPException 404: If team member not found or doesn't belong to your tenant
    """
    return team_member_service.get_team_member(
        db=db,
        team_member_id=team_member_id,
        tenant_id=_tenant_id
    )


@router.put("/{team_member_id}", response_model=TeamMemberResponse)
def update_team_member(
    team_member_id: int,
    team_member_data: TeamMemberUpdate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Update an existing team member.
    
    The tenant is automatically identified from the JWT token.
    Only allows updating team members belonging to your tenant.
    
    Args:
        team_member_id: ID of the team member to update
        team_member_data: Team member update data (partial updates supported)
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT, used internally)
    
    Returns:
        Updated team member
    
    Raises:
        HTTPException 404: If team member not found or doesn't belong to your tenant
        HTTPException 400: If email already exists for this tenant
    """
    return team_member_service.update_team_member(
        db=db,
        team_member_id=team_member_id,
        team_member_data=team_member_data,
        tenant_id=_tenant_id
    )


@router.delete("/{team_member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(
    team_member_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Delete a team member.
    
    The tenant is automatically identified from the JWT token.
    Only allows deleting team members belonging to your tenant.
    
    Args:
        team_member_id: ID of the team member to delete
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT, used internally)
    
    Raises:
        HTTPException 404: If team member not found or doesn't belong to your tenant
    """
    team_member_service.delete_team_member(
        db=db,
        team_member_id=team_member_id,
        tenant_id=_tenant_id
    )
    return None
