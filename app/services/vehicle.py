from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud import vehicle as vehicle_crud
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.models.vehicle import Vehicle


class VehicleService:
    """
    Service layer for vehicle business logic.
    
    This layer handles business rules, validation, and coordination
    of CRUD operations.
    """
    
    def __init__(self):
        self.crud = vehicle_crud
    
    def get_vehicle(
        self,
        db: Session,
        vehicle_id: int,
        tenant_id: int
    ) -> Vehicle:
        """
        Get a vehicle by ID with tenant isolation.
        
        Args:
            db: Database session
            vehicle_id: Vehicle ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            Vehicle instance
            
        Raises:
            HTTPException 404: If vehicle not found
        """
        vehicle = self.crud.get(db=db, id=vehicle_id, tenant_id=tenant_id)
        
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        
        return vehicle
    
    def get_vehicles(
        self,
        db: Session,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vehicle]:
        """
        Get all vehicles with tenant isolation.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Vehicle instances
        """
        return self.crud.get_multi(db=db, skip=skip, limit=limit, tenant_id=tenant_id)
    
    def create_vehicle(
        self,
        db: Session,
        vehicle_data: VehicleCreate,
        tenant_id: int
    ) -> Vehicle:
        """
        Create a new vehicle.
        
        Args:
            db: Database session
            vehicle_data: Vehicle creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created Vehicle instance
        """
        return self.crud.create(db=db, obj_in=vehicle_data, tenant_id=tenant_id)
    
    def update_vehicle(
        self,
        db: Session,
        vehicle_id: int,
        vehicle_data: VehicleUpdate,
        tenant_id: int
    ) -> Vehicle:
        """
        Update a vehicle.
        
        Args:
            db: Database session
            vehicle_id: Vehicle ID
            vehicle_data: Vehicle update data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Updated Vehicle instance
            
        Raises:
            HTTPException 404: If vehicle not found
        """
        # Get existing vehicle
        vehicle = self.get_vehicle(db=db, vehicle_id=vehicle_id, tenant_id=tenant_id)
        
        # Update the vehicle
        return self.crud.update(db=db, db_obj=vehicle, obj_in=vehicle_data)
    
    def delete_vehicle(
        self,
        db: Session,
        vehicle_id: int,
        tenant_id: int
    ) -> None:
        """
        Delete a vehicle.
        
        Args:
            db: Database session
            vehicle_id: Vehicle ID
            tenant_id: Tenant ID for isolation
            
        Raises:
            HTTPException 404: If vehicle not found
        """
        deleted = self.crud.delete(db=db, id=vehicle_id, tenant_id=tenant_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )


# Create a singleton instance
vehicle_service = VehicleService()
