from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime
from enum import Enum


class ScheduleBlockType(str, Enum):
    """Type of schedule block - extensible for future use cases"""
    route = "route"
    break_time = "break"
    # Future: shift, meeting, task, etc.


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
    metadata: Optional[dict] = None  # Additional data (route_id, stops_count, etc.)


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
