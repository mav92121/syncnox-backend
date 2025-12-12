from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

# RouteStop Schemas
class RouteStopBase(BaseModel):
    job_id: Optional[int] = None
    sequence_order: Optional[int] = None
    stop_type: Optional[str] = None
    planned_arrival_time: Optional[datetime] = None
    planned_departure_time: Optional[datetime] = None
    estimated_distance_from_prev: Optional[float] = None
    actual_arrival_time: Optional[datetime] = None
    actual_departure_time: Optional[datetime] = None
    geofence_entered_at: Optional[datetime] = None

class RouteStopCreate(RouteStopBase):
    route_id: int

class RouteStopUpdate(BaseModel):
    job_id: Optional[int] = None
    sequence_order: Optional[int] = None
    stop_type: Optional[str] = None
    planned_arrival_time: Optional[datetime] = None
    planned_departure_time: Optional[datetime] = None
    estimated_distance_from_prev: Optional[float] = None
    actual_arrival_time: Optional[datetime] = None
    actual_departure_time: Optional[datetime] = None
    geofence_entered_at: Optional[datetime] = None

class RouteStopResponse(RouteStopBase):
    id: int
    route_id: int

    class Config:
        from_attributes = True

# Route Schemas
class RouteBase(BaseModel):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    depot_id: Optional[int] = None
    optimization_request_id: Optional[int] = None
    status: Optional[str] = None
    scheduled_date: Optional[date] = None
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    route_polyline: Optional[str] = None
    rating: Optional[float] = None
    additional_notes: Optional[str] = None

class RouteCreate(RouteBase):
    pass

class RouteUpdate(BaseModel):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    depot_id: Optional[int] = None
    status: Optional[str] = None
    scheduled_date: Optional[date] = None
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    route_polyline: Optional[str] = None
    rating: Optional[float] = None
    additional_notes: Optional[str] = None

class RouteResponse(RouteBase):
    id: int
    stops: List[RouteStopResponse] = []

    class Config:
        from_attributes = True

# Analytics Schemas
class TeamMemberSummary(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None

class RouteAnalyticsItem(BaseModel):
    id: int  # Optimization Request ID
    optimization_id: int
    name: str
    status: str
    
    # Metrics
    total_distance: float
    total_time: float
    progress_percentage: int
    
    # Stop Counts
    total_stops: int
    completed_stops: int
    failed_stops: int
    attempted_stops: int
    
    # Assignments
    assigned_team_members: List[TeamMemberSummary]
    
    # Meta
    rating: Optional[float] = None
    scheduled_date: date
    created_at: datetime

    class Config:
        from_attributes = True
