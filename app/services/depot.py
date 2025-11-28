from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud import depot as depot_crud
from app.schemas.depot import DepotCreate, DepotUpdate
from app.models.depot import Depot


class DepotService:
    """
    Service layer for depot business logic.
    
    This layer handles business rules, validation, and coordination
    of CRUD operations.
    """
    
    def __init__(self):
        self.crud = depot_crud
    
    def get_depot(
        self,
        db: Session,
        depot_id: int,
        tenant_id: int
    ) -> Depot:
        """
        Get a depot by ID with tenant isolation.
        
        Args:
            db: Database session
            depot_id: Depot ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            Depot instance
            
        Raises:
            HTTPException 404: If depot not found
        """
        depot = self.crud.get(db=db, id=depot_id, tenant_id=tenant_id)
        
        if not depot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Depot not found"
            )
        
        return depot
    
    def get_depots(
        self,
        db: Session,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Depot]:
        """
        Get all depots with tenant isolation.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Depot instances
        """
        return self.crud.get_multi(db=db, skip=skip, limit=limit, tenant_id=tenant_id)
    
    def create_depot(
        self,
        db: Session,
        depot_data: DepotCreate,
        tenant_id: int
    ) -> Depot:
        """
        Create a new depot.
        
        Args:
            db: Database session
            depot_data: Depot creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created Depot instance
        """
        return self.crud.create(db=db, obj_in=depot_data, tenant_id=tenant_id)
    
    def update_depot(
        self,
        db: Session,
        depot_id: int,
        depot_data: DepotUpdate,
        tenant_id: int
    ) -> Depot:
        """
        Update a depot.
        
        Args:
            db: Database session
            depot_id: Depot ID
            depot_data: Depot update data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Updated Depot instance
            
        Raises:
            HTTPException 404: If depot not found
        """
        # Get existing depot
        depot = self.get_depot(db=db, depot_id=depot_id, tenant_id=tenant_id)
        
        # Update the depot
        return self.crud.update(db=db, db_obj=depot, obj_in=depot_data)
    
    def delete_depot(
        self,
        db: Session,
        depot_id: int,
        tenant_id: int
    ) -> None:
        """
        Delete a depot.
        
        Args:
            db: Database session
            depot_id: Depot ID
            tenant_id: Tenant ID for isolation
            
        Raises:
            HTTPException 404: If depot not found
        """
        deleted = self.crud.delete(db=db, id=depot_id, tenant_id=tenant_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Depot not found"
            )


# Create a singleton instance
depot_service = DepotService()
