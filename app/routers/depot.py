from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.depot import DepotCreate, DepotUpdate, DepotResponse
from app.services.depot import depot_service
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger

router = APIRouter()


@router.post("", response_model=DepotResponse, status_code=status.HTTP_201_CREATED)
def create_depot(
    depot_data: DepotCreate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Create a new depot.
    
    The tenant is automatically identified from the JWT token.
    
    Args:
        depot_data: Depot creation data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Created depot
    """
    try:
        logger.info(f"Creating depot: name={depot_data.name}, tenant_id={_tenant_id}")
        result = depot_service.create_depot(
            db=db,
            depot_data=depot_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Depot created successfully: id={result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating depot: {type(e).__name__}: {str(e)}")
        raise

@router.get("", response_model=List[DepotResponse])
def get_depots(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve all depots for your tenant.
    
    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        List of depots belonging to your tenant
    """
    return depot_service.get_depots(
        db=db,
        tenant_id=_tenant_id,
        skip=skip,
        limit=limit
    )


@router.get("/{depot_id}", response_model=DepotResponse)
def get_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve a specific depot by ID.
    
    Args:
        depot_id: Depot ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Depot details
        
    Raises:
        HTTPException 404: If depot not found
    """
    return depot_service.get_depot(
        db=db,
        depot_id=depot_id,
        tenant_id=_tenant_id
    )


@router.put("/{depot_id}", response_model=DepotResponse)
def update_depot(
    depot_id: int,
    depot_data: DepotUpdate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Update an existing depot.
    
    Args:
        depot_id: Depot ID
        depot_data: Depot update data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Updated depot
        
    Raises:
        HTTPException 404: If depot not found
    """
    return depot_service.update_depot(
        db=db,
        depot_id=depot_id,
        depot_data=depot_data,
        tenant_id=_tenant_id
    )


@router.delete("/{depot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Delete a depot.
    
    Args:
        depot_id: Depot ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Raises:
        HTTPException 404: If depot not found
    """
    depot_service.delete_depot(
        db=db,
        depot_id=depot_id,
        tenant_id=_tenant_id
    )
    return None
