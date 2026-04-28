from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.models.vehicle import VehicleType


class LoadConstraint(BaseModel):
    constraint_type: str  # e.g., "weight", "volume", "item_count", "pallets", "distance", "duration", "custom"
    max_value: float
    unit: str
    label: Optional[str] = None  # Used when constraint_type == "custom"

class VehicleBase(BaseModel):
    name: str
    team_member_id: Optional[int] = None
    load_constraints: Optional[List[LoadConstraint]] = []
    type: Optional[VehicleType] = None
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    team_member_id: Optional[int] = None
    load_constraints: Optional[List[LoadConstraint]] = None
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
