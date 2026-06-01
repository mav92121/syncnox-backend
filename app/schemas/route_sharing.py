"""
Pydantic schemas for the route-sharing / driver-route endpoints.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from app.schemas.common import Location


# ------------------------------------------------------------------ #
# Shared route dispatch
# ------------------------------------------------------------------ #

class ShareRouteResponse(BaseModel):
    shared_count: int
    driver_ids: List[int]
    online_drivers: List[int]


# ------------------------------------------------------------------ #
# Driver: my-route
# ------------------------------------------------------------------ #

class StopJobDetail(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    address_formatted: Optional[str] = None
    job_type: Optional[str] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    service_duration: Optional[int] = None
    additional_notes: Optional[str] = None
    status: Optional[str] = None
    location: Optional[Location] = None

    class Config:
        from_attributes = True

    @field_validator("location", mode="before")
    @classmethod
    def serialize_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v


class RouteStopDetail(BaseModel):
    id: int
    sequence_order: Optional[int] = None
    stop_type: Optional[str] = None
    planned_arrival_time: Optional[datetime] = None
    actual_arrival_time: Optional[datetime] = None
    actual_departure_time: Optional[datetime] = None
    job: Optional[StopJobDetail] = None
    location: Optional[Location] = None
    address_formatted: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator("location", mode="before")
    @classmethod
    def serialize_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v


class DriverRouteResponse(BaseModel):
    route_id: int
    scheduled_date: Optional[date] = None
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    assignment_status: str
    stops: List[RouteStopDetail] = []

    class Config:
        from_attributes = True


# ------------------------------------------------------------------ #
# Stop status update
# ------------------------------------------------------------------ #

class StopStatusUpdate(BaseModel):
    status: str  # "completed" | "failed"
