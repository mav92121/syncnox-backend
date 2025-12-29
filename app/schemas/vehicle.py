from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.vehicle import VehicleType

class VehicleBase(BaseModel):
    name: str
    team_member_id: Optional[int] = None
    capacity_weight: Optional[float] = None
    capacity_volume: Optional[float] = None
    type: Optional[VehicleType] = None
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    team_member_id: Optional[int] = None
    capacity_weight: Optional[float] = None
    capacity_volume: Optional[float] = None
    type: Optional[VehicleType] = None
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None

class VehicleResponse(VehicleBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
