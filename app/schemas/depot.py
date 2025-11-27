from pydantic import BaseModel
from typing import Optional, Dict, Any
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

    class Config:
        from_attributes = True
