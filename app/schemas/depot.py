from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from app.schemas.common import Location, Address

class DepotBase(BaseModel):
    name: str
    location: Optional[Location] = None
    address: Optional[Address] = None

class DepotCreate(DepotBase):
    pass

class DepotUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[Location] = None
    address: Optional[Address] = None

class DepotResponse(DepotBase):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True

    @field_validator("location", mode="before")
    @classmethod
    def serialize_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v
