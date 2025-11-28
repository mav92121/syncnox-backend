from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.depot import Depot
from app.schemas.depot import DepotCreate, DepotUpdate


class CRUDDepot(CRUDBase[Depot, DepotCreate, DepotUpdate]):
    """
    CRUD operations for Depot model.
    
    Inherits all standard CRUD operations from CRUDBase.
    """
    
    def create(
        self,
        db: Session,
        *,
        obj_in: DepotCreate,
        tenant_id: int
    ) -> Depot:
        """
        Create a new depot with location conversion.
        """
        obj_data = obj_in.model_dump()
        
        # Convert location dict to WKT string if present
        if obj_data.get("location"):
            loc = obj_data["location"]
            # GeoAlchemy2 expects WKT format: POINT(x y) -> POINT(lng lat)
            obj_data["location"] = f"POINT({loc['lng']} {loc['lat']})"
            
        db_obj = self.model(tenant_id=tenant_id, **obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Depot,
        obj_in: DepotUpdate | Dict[str, Any]
    ) -> Depot:
        """
        Update a depot with location conversion.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        # Convert location dict to WKT string if present
        if update_data.get("location"):
            loc = update_data["location"]
            # GeoAlchemy2 expects WKT format: POINT(x y) -> POINT(lng lat)
            update_data["location"] = f"POINT({loc['lng']} {loc['lat']})"
            
        return super().update(db=db, db_obj=db_obj, obj_in=update_data)


# Create a singleton instance
depot = CRUDDepot(Depot)
