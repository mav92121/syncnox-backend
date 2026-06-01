"""
Router for real-time route sharing:
  - POST /api/optimization/{opt_id}/share     → manager dispatches all routes
  - WS   /ws/driver/{driver_id}               → driver mobile app channel
  - WS   /ws/dispatch/{tenant_id}             → web dispatch channel
  - GET  /api/driver/my-route                 → driver fetches assigned route
  - POST /api/driver/my-route/acknowledge     → driver acknowledges receipt
  - POST /api/driver/stops/{stop_id}/status   → driver marks stop complete/failed
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status, Query
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.core.tenant_context import get_tenant_id
from app.core.ws_manager import ws_manager
from app.database import get_db
from app.dependencies import get_current_user
from app.models.team_member import TeamMember
from app.schemas.route_sharing import (
    DriverRouteResponse,
    RouteStopDetail,
    StopJobDetail,
    StopStatusUpdate,
    ShareRouteResponse,
)
from app.services.route_sharing import route_sharing_service
from app.services.team_member import team_member_service

router = APIRouter()


# ------------------------------------------------------------------ #
# Helper: resolve driver from activation-code header
# ------------------------------------------------------------------ #

def _get_driver(
    activation_code: Optional[str] = Header(None, alias="activation-code"),
    db: Session = Depends(get_db),
) -> TeamMember:
    if not activation_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="activation-code header is required",
        )
    return team_member_service.verify_driver(db=db, activation_code=activation_code)


# ================================================================== #
# Manager endpoint
# ================================================================== #

@router.post(
    "/optimization/{optimization_request_id}/share",
    response_model=ShareRouteResponse,
    status_code=status.HTTP_200_OK,
    tags=["Route Sharing"],
)
async def share_optimization_routes(
    optimization_request_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ShareRouteResponse:
    """
    Dispatch all routes in an optimization request to their assigned drivers simultaneously.
    Sends a 'route_assigned' WebSocket event to each connected driver.
    """
    result = route_sharing_service.share_optimization_routes(
        db=db,
        optimization_request_id=optimization_request_id,
        tenant_id=tenant_id,
    )
    driver_ids: list[int] = result["driver_ids"]
    online_drivers: list[int] = []

    # Broadcast to every driver in parallel
    async def _notify(driver_id: int) -> None:
        delivered = await ws_manager.send_to_driver(driver_id, {
            "event": "route_assigned",
            "optimization_request_id": optimization_request_id,
        })
        if delivered:
            online_drivers.append(driver_id)

    await asyncio.gather(*[_notify(did) for did in driver_ids])

    logger.info(
        f"Shared opt_req {optimization_request_id}: "
        f"{len(driver_ids)} drivers, {len(online_drivers)} online"
    )
    return ShareRouteResponse(
        shared_count=len(driver_ids),
        driver_ids=driver_ids,
        online_drivers=online_drivers,
    )


# ================================================================== #
# WebSocket: Driver channel
# ================================================================== #

@router.websocket("/ws/driver/{driver_id}")
async def driver_ws(
    websocket: WebSocket,
    driver_id: int,
    code: str = Query(..., alias="code"),
    db: Session = Depends(get_db),
) -> None:
    """
    Persistent WebSocket channel for a driver's mobile app.
    Auth: activation code passed as ?code= query parameter.
    """
    # Authenticate before accepting
    try:
        driver = team_member_service.verify_driver(db=db, activation_code=code)
        if driver.id != driver_id:
            await websocket.close(code=4003)
            return
    except HTTPException:
        await websocket.close(code=4001)
        return

    await ws_manager.connect_driver(driver_id, websocket)
    try:
        while True:
            # Keep connection alive; drivers only receive, not send (for now)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_driver(driver_id)
        logger.info(f"Driver {driver_id} WebSocket disconnected")


# ================================================================== #
# WebSocket: Dispatch channel
# ================================================================== #

@router.websocket("/ws/dispatch/{tenant_id}")
async def dispatch_ws(
    websocket: WebSocket,
    tenant_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """
    Persistent WebSocket channel for the web dispatch dashboard.
    Auth: JWT passed as ?token= query parameter (browsers cannot set WS headers).
    """
    from app.dependencies import decode_access_token
    try:
        user = decode_access_token(token=token, db=db)
        if user.tenant_id != tenant_id:
            await websocket.close(code=4003)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect_dispatch(tenant_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_dispatch(tenant_id, websocket)


# ================================================================== #
# Driver REST endpoints
# ================================================================== #

@router.get(
    "/driver/my-route",
    response_model=DriverRouteResponse,
    tags=["Driver"],
)
def get_my_route(
    driver: TeamMember = Depends(_get_driver),
    db: Session = Depends(get_db),
) -> DriverRouteResponse:
    """Return the driver's currently assigned active route with all stops."""
    data = route_sharing_service.get_driver_route(db=db, driver_id=driver.id)
    route = data["route"]

    stops = [
        RouteStopDetail(
            id=s.id,
            sequence_order=s.sequence_order,
            stop_type=s.stop_type,
            planned_arrival_time=s.planned_arrival_time,
            actual_arrival_time=s.actual_arrival_time,
            actual_departure_time=s.actual_departure_time,
            job=StopJobDetail.model_validate(s.job) if s.job else None,
            location=s.location,
            address_formatted=s.address_formatted,
        )
        for s in sorted(route.stops, key=lambda s: s.sequence_order or 0)
    ]

    return DriverRouteResponse(
        route_id=route.id,
        scheduled_date=route.scheduled_date,
        total_distance_meters=route.total_distance_meters,
        total_duration_seconds=route.total_duration_seconds,
        assignment_status=data["assignment_status"],
        stops=stops,
    )


@router.post(
    "/driver/my-route/acknowledge",
    status_code=status.HTTP_200_OK,
    tags=["Driver"],
)
def acknowledge_my_route(
    driver: TeamMember = Depends(_get_driver),
    db: Session = Depends(get_db),
) -> dict:
    """Driver acknowledges receipt of the assigned route."""
    route_sharing_service.acknowledge_route(db=db, driver_id=driver.id)
    return {"status": "acknowledged"}


@router.post(
    "/driver/stops/{stop_id}/status",
    status_code=status.HTTP_200_OK,
    tags=["Driver"],
)
async def update_stop_status(
    stop_id: int,
    body: StopStatusUpdate,
    driver: TeamMember = Depends(_get_driver),
    db: Session = Depends(get_db),
) -> dict:
    """
    Driver marks a stop as 'completed' or 'failed'.
    Broadcasts a stop_completed/stop_failed event to the dispatch WebSocket channel.
    """
    result = route_sharing_service.update_stop_status(
        db=db,
        stop_id=stop_id,
        driver_id=driver.id,
        new_status=body.status,
    )

    # Reverse push to the web dispatch dashboard
    await ws_manager.broadcast_to_dispatch(result["tenant_id"], {
        "event": "stop_updated",
        "route_id": result["route_id"],
        "stop_id": result["stop_id"],
        "new_status": result["new_status"],
        "driver_id": result["driver_id"],
        "driver_name": result["driver_name"],
        "progress_percentage": result["progress_percentage"],
    })

    return {"status": "ok", "progress_percentage": result["progress_percentage"]}
