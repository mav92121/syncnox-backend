from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.services.vehicle import vehicle_service
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger

router = APIRouter()

@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    vehicle_data: VehicleCreate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Create a new vehicle.
    
    The tenant is automatically identified from the JWT token.
    
    Args:
        vehicle_data: Vehicle creation data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Created vehicle
    """
    try:
        logger.info(f"Creating vehicle: name={vehicle_data.name}, tenant_id={_tenant_id}")
        result = vehicle_service.create_vehicle(
            db=db,
            vehicle_data=vehicle_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Vehicle created successfully: id={result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating vehicle: {type(e).__name__}: {str(e)}")
        raise


@router.get("", response_model=List[VehicleResponse])
def get_vehicles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve all vehicles for your tenant.
    
    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        List of vehicles belonging to your tenant
    """
    return vehicle_service.get_vehicles(
        db=db,
        tenant_id=_tenant_id,
        skip=skip,
        limit=limit
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve a specific vehicle by ID.
    
    Args:
        vehicle_id: Vehicle ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Vehicle details
        
    Raises:
        HTTPException 404: If vehicle not found
    """
    return vehicle_service.get_vehicle(
        db=db,
        vehicle_id=vehicle_id,
        tenant_id=_tenant_id
    )


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Update an existing vehicle.
    
    Args:
        vehicle_id: Vehicle ID
        vehicle_data: Vehicle update data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Updated vehicle
        
    Raises:
        HTTPException 404: If vehicle not found
    """
    return vehicle_service.update_vehicle(
        db=db,
        vehicle_id=vehicle_id,
        vehicle_data=vehicle_data,
        tenant_id=_tenant_id
    )


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Delete a vehicle.
    
    Args:
        vehicle_id: Vehicle ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Raises:
        HTTPException 404: If vehicle not found
    """
    vehicle_service.delete_vehicle(
        db=db,
        vehicle_id=vehicle_id,
        tenant_id=_tenant_id
    )
    return None
