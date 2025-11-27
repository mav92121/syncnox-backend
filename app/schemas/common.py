from pydantic import BaseModel, Field
from typing import Optional

class Location(BaseModel):
    lat: float = Field(..., description="Latitude", ge=-90, le=90)
    lng: float = Field(..., description="Longitude", ge=-180, le=180)

class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    formatted_address: Optional[str] = None
