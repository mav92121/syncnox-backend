from typing import Optional
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
    pass


# Create a singleton instance
vehicle = CRUDVehicle(Vehicle)
