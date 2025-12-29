from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import time, datetime
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from app.models.team_member import TeamMemberStatus, TeamMemberRole
from app.schemas.common import Location

class TeamMemberBase(BaseModel):
    vehicle_id: Optional[int] = None
    vehicle: Optional[str] = None
    status: Optional[TeamMemberStatus] = None
    name: str = Field(..., min_length=1, max_length=255)
    role_type: Optional[TeamMemberRole] = TeamMemberRole.driver
    external_identifier: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    navigation_link_format: Optional[str] = Field("google_maps", max_length=50)
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    allowed_overtime: Optional[bool] = False
    max_distance: Optional[float] = None
    break_time_start: Optional[time] = None
    break_time_end: Optional[time] = None
    skills: Optional[List[str]] = Field(None, max_length=50)
    fixed_cost_for_driver: Optional[float] = None
    cost_per_km: Optional[float] = None
    cost_per_hr: Optional[float] = None
    cost_per_hr_overtime: Optional[float] = None
    start_location: Optional[Location] = None
    start_address: Optional[str] = None
    end_location: Optional[Location] = None
    end_address: Optional[str] = None

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    vehicle: Optional[str] = None
    status: Optional[TeamMemberStatus] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role_type: Optional[TeamMemberRole] = None
    external_identifier: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    navigation_link_format: Optional[str] = Field(None, max_length=50)
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    allowed_overtime: Optional[bool] = None
    max_distance: Optional[float] = None
    break_time_start: Optional[time] = None
    break_time_end: Optional[time] = None
    skills: Optional[List[str]] = Field(None, max_length=50)
    fixed_cost_for_driver: Optional[float] = None
    cost_per_km: Optional[float] = None
    cost_per_hr: Optional[float] = None
    cost_per_hr_overtime: Optional[float] = None
    start_location: Optional[Location] = None
    start_address: Optional[str] = None
    end_location: Optional[Location] = None
    end_address: Optional[str] = None

class TeamMemberResponse(TeamMemberBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("start_location", mode="before")
    @classmethod
    def serialize_start_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v

    @field_validator("end_location", mode="before")
    @classmethod
    def serialize_end_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v
