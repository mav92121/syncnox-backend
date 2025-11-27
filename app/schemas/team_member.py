from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import time
from app.models.team_member import TeamMemberStatus, TeamMemberRole

class TeamMemberBase(BaseModel):
    vehicle_id: Optional[int] = None
    status: Optional[TeamMemberStatus] = None
    name: str
    role_type: Optional[TeamMemberRole] = TeamMemberRole.driver
    external_identifier: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    navigation_link_format: Optional[str] = "google_maps"
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    allowed_overtime: Optional[bool] = False
    max_distance: Optional[float] = None
    break_time_start: Optional[time] = None
    break_time_end: Optional[time] = None
    skills: Optional[List[str]] = None
    fixed_cost_for_driver: Optional[float] = None
    cost_per_km: Optional[float] = None
    cost_per_hr: Optional[float] = None
    cost_per_hr_overtime: Optional[float] = None

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    status: Optional[TeamMemberStatus] = None
    name: Optional[str] = None
    role_type: Optional[TeamMemberRole] = None
    external_identifier: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    navigation_link_format: Optional[str] = None
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    allowed_overtime: Optional[bool] = None
    max_distance: Optional[float] = None
    break_time_start: Optional[time] = None
    break_time_end: Optional[time] = None
    skills: Optional[List[str]] = None
    fixed_cost_for_driver: Optional[float] = None
    cost_per_km: Optional[float] = None
    cost_per_hr: Optional[float] = None
    cost_per_hr_overtime: Optional[float] = None

class TeamMemberResponse(TeamMemberBase):
    id: int

    class Config:
        from_attributes = True
