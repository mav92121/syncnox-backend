"""
Pydantic schemas for per-driver route operations.
"""

from pydantic import BaseModel, Field


class AddStopRequest(BaseModel):
    job_id: int = Field(..., description="ID of the draft job to add to this route")


class SwapDriverRequest(BaseModel):
    new_driver_id: int = Field(..., description="Team member ID of the new driver")


class RouteOperationResponse(BaseModel):
    """
    Unified response for all route operations.

    The frontend should:
    - On success: start polling the optimization request for status updates
    - On reverse (sync): just refresh the optimization data
    """
    success: bool
    message: str
