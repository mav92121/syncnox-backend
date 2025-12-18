from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.models.optimization_request import OptimizationGoal, OptimizationStatus


class OptimizationRequestCreate(BaseModel):
    """Schema for creating an optimization request."""
    route_name: str = Field(..., min_length=1, max_length=255, description="User-friendly name for the optimization (e.g., 'dec 1')")
    depot_id: int = Field(..., description="ID of the depot to optimize from")
    job_ids: List[int] = Field(..., min_length=1, description="List of job IDs to include in optimization")
    team_member_ids: List[int] = Field(..., min_length=1, description="List of team member IDs available for routing")
    scheduled_date: date = Field(..., description="Date for which to optimize routes")
    optimization_goal: OptimizationGoal = Field(
        default=OptimizationGoal.MINIMUM_TIME,
        description="Optimization objective: minimize time or distance"
    )



class OptimizationRequestUpdate(BaseModel):
    """Schema for updating an optimization request."""
    route_name: Optional[str] = Field(None, min_length=1, max_length=255, description="New name for the optimization route")


class OptimizationRequestResponse(BaseModel):
    """Schema for optimization request response."""
    id: int
    tenant_id: int
    route_name: str
    depot_id: int
    job_ids: List[int]
    team_member_ids: List[int]
    scheduled_date: date
    optimization_goal: OptimizationGoal
    status: OptimizationStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
