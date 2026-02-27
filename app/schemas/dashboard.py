from pydantic import BaseModel
from typing import List


class DashboardKPI(BaseModel):
    total_jobs: int = 0
    active_routes: int = 0
    completed_jobs: int = 0
    scheduled_jobs: int = 0
    total_drivers: int = 0
    total_depots: int = 0


class OptimizationImpact(BaseModel):
    total_distance_saved_km: float = 0.0
    total_time_saved_hours: float = 0.0
    vehicles_saved: int = 0


class RecentRoute(BaseModel):
    key: str
    name: str
    driver: str
    stops: int = 0
    completed: int = 0
    status: str


class TopDriver(BaseModel):
    name: str
    completion_rate: float = 0.0
    on_time_rate: float = 0.0


class UpcomingDay(BaseModel):
    date: str
    jobs: int = 0
    routes: int = 0


class DashboardResponse(BaseModel):
    kpi: DashboardKPI
    optimization_impact: OptimizationImpact
    recent_routes: List[RecentRoute]
    top_drivers: List[TopDriver]
    upcoming: List[UpcomingDay]

    class Config:
        from_attributes = True
