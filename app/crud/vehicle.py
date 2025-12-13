from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class CRUDVehicle(CRUDBase[Vehicle, VehicleCreate, VehicleUpdate]):
    """
    CRUD operations for Vehicle model.
    
    Inherits all standard CRUD operations from CRUDBase.
    """
    
    def get_multi_by_ids(
        self,
        db: Session,
        *,
        ids: List[int],
        tenant_id: int
    ) -> List[Vehicle]:
        """
        Bulk fetch vehicles by IDs.
        
        Args:
            db: Database session
            ids: List of vehicle IDs to fetch
            tenant_id: Tenant ID for isolation
            
        Returns:
            List of Vehicle instances
        """
        stmt = select(Vehicle).where(
            Vehicle.id.in_(ids),
            Vehicle.tenant_id == tenant_id
        )
        result = db.execute(stmt)
        return list(result.scalars().all())


# Create a singleton instance
vehicle = CRUDVehicle(Vehicle)
