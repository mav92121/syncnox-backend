from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime
from enum import Enum


class ScheduleBlockType(str, Enum):
    """Type of schedule block - extensible for future use cases"""
    route = "route"
    break_time = "break"
    job = "job"        # Individual job stop
    idle = "idle"      # Idle/waiting time
    depot = "depot"    # Depot stop
    # Future: shift, meeting, task, etc.


class ScheduleBlockMetadata(BaseModel):
    """Extended metadata for schedule blocks."""
    route_id: Optional[int] = None
    stops_count: Optional[int] = None
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    driver_id: Optional[int] = None
    # Break-specific
    break_duration_minutes: Optional[int] = None
    break_location_address: Optional[str] = None
    # Job-specific
    service_duration_minutes: Optional[int] = None
    job_id: Optional[int] = None
    address: Optional[str] = None
    # Idle-specific
    idle_duration_minutes: Optional[int] = None


class ScheduleBlock(BaseModel):
    """
    A single block on the schedule timeline.
    Generalized to support routes, breaks, and future block types.
    """
    id: str                          # Unique identifier (e.g., "route_123", "break_1")
    type: ScheduleBlockType
    start_time: datetime             # UTC timestamp
    end_time: datetime               # UTC timestamp
    title: str                       # Display title (route name, "Break", etc.)
    status: Optional[str] = None     # scheduled, in_transit, completed, failed
    metadata: Optional[ScheduleBlockMetadata] = None  # Extended metadata


class ResourceSchedule(BaseModel):
    """
    Schedule for a single resource (driver, employee, etc.)
    """
    resource_id: int
    resource_name: str
    resource_type: str               # "driver", "employee", etc.
    blocks: List[ScheduleBlock] = []


class ScheduleResponse(BaseModel):
    """
    Response containing all resource schedules for a given date.
    """
    date: date
    resources: List[ResourceSchedule]
