from pydantic import BaseModel
from typing import Optional
from app.models.vehicle import VehicleType

class VehicleBase(BaseModel):
    name: str
    capacity_weight: Optional[float] = None
    capacity_volume: Optional[float] = None
    type: Optional[VehicleType] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    capacity_weight: Optional[float] = None
    capacity_volume: Optional[float] = None
    type: Optional[VehicleType] = None

class VehicleResponse(VehicleBase):
    id: int

    class Config:
        from_attributes = True
