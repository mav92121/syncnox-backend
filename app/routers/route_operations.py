"""
API Router for per-driver route operations.

All endpoints operate on a specific route within a completed optimization:
  POST /optimization/requests/{request_id}/routes/{route_index}/add-stop
  POST /optimization/requests/{request_id}/routes/{route_index}/swap-driver
  POST /optimization/requests/{request_id}/routes/{route_index}/reverse
  POST /optimization/requests/{request_id}/routes/{route_index}/re-optimize
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.schemas.route_operations import (
    AddStopRequest,
    SwapDriverRequest,
    RouteOperationResponse,
)
from app.services.route_operations import route_operations_service

router = APIRouter()


@router.post(
    "/requests/{request_id}/routes/{route_index}/add-stop",
    response_model=RouteOperationResponse,
)
def add_stop_to_route(
    request_id: int,
    route_index: int,
    payload: AddStopRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Add a draft job to a specific driver's route and re-optimize."""
    return route_operations_service.add_stop(
        db=db,
        optimization_request_id=request_id,
        route_index=route_index,
        job_id=payload.job_id,
        tenant_id=tenant_id,
    )


@router.post(
    "/requests/{request_id}/routes/{route_index}/swap-driver",
    response_model=RouteOperationResponse,
)
def swap_route_driver(
    request_id: int,
    route_index: int,
    payload: SwapDriverRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Swap the driver on a route and re-optimize for new driver's constraints."""
    return route_operations_service.swap_driver(
        db=db,
        optimization_request_id=request_id,
        route_index=route_index,
        new_driver_id=payload.new_driver_id,
        tenant_id=tenant_id,
    )


@router.post(
    "/requests/{request_id}/routes/{route_index}/reverse",
    response_model=RouteOperationResponse,
)
def reverse_route(
    request_id: int,
    route_index: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Reverse the stop order of a driver's route (synchronous)."""
    return route_operations_service.reverse_route(
        db=db,
        optimization_request_id=request_id,
        route_index=route_index,
        tenant_id=tenant_id,
    )


@router.post(
    "/requests/{request_id}/routes/{route_index}/re-optimize",
    response_model=RouteOperationResponse,
)
def re_optimize_route(
    request_id: int,
    route_index: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Re-optimize a single driver's route via full VRP re-run (async)."""
    return route_operations_service.re_optimize_route(
        db=db,
        optimization_request_id=request_id,
        route_index=route_index,
        tenant_id=tenant_id,
    )
