"""
Service layer for route-sharing and driver route operations.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging_config import logger
from app.models.job import Job, JobStatus
from app.models.optimization_request import OptimizationRequest
from app.models.route import Route, RouteStop
from app.models.route_assignment import RouteAssignment, RouteAssignmentStatus
from app.models.team_member import TeamMember


class RouteSharingService:
    # ------------------------------------------------------------------ #
    # Manager: share optimization request → all drivers
    # ------------------------------------------------------------------ #

    def share_optimization_routes(
        self,
        db: Session,
        optimization_request_id: int,
        tenant_id: int,
    ) -> dict:
        """
        Upsert a route_assignment row for every (route, driver) pair in the
        optimization request.  Returns the list of driver IDs so the router
        can fire WebSocket events.
        """
        opt_req = db.get(OptimizationRequest, optimization_request_id)
        if not opt_req or opt_req.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Optimization request not found")

        routes: list[Route] = (
            db.execute(
                select(Route).where(
                    Route.optimization_request_id == optimization_request_id,
                    Route.driver_id.is_not(None),
                )
            )
            .scalars()
            .all()
        )

        if not routes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No routes with assigned drivers found in this optimization request",
            )

        now = datetime.now(timezone.utc)
        driver_ids: list[int] = []

        for route in routes:
            driver_ids.append(route.driver_id)

            # Mark any other active assignments for this driver as completed
            db.query(RouteAssignment).filter(
                RouteAssignment.driver_id == route.driver_id,
                RouteAssignment.route_id != route.id,
                RouteAssignment.status.in_([
                    RouteAssignmentStatus.pending,
                    RouteAssignmentStatus.acknowledged,
                    RouteAssignmentStatus.in_progress,
                ])
            ).update(
                {
                    RouteAssignment.status: RouteAssignmentStatus.completed,
                    RouteAssignment.completed_at: now
                },
                synchronize_session=False
            )

            # Try to find an existing assignment (re-share scenario)
            existing = db.execute(
                select(RouteAssignment).where(
                    RouteAssignment.route_id == route.id,
                    RouteAssignment.driver_id == route.driver_id,
                )
            ).scalar_one_or_none()

            if existing:
                # Re-share: reset status and update shared_at
                existing.status = RouteAssignmentStatus.pending
                existing.shared_at = now
                existing.acknowledged_at = None
                existing.completed_at = None
                logger.info(f"Re-sharing route {route.id} to driver {route.driver_id}")
            else:
                assignment = RouteAssignment(
                    route_id=route.id,
                    driver_id=route.driver_id,
                    tenant_id=tenant_id,
                    status=RouteAssignmentStatus.pending,
                    shared_at=now,
                )
                db.add(assignment)
                logger.info(f"Sharing route {route.id} to driver {route.driver_id}")

        db.commit()
        return {"driver_ids": driver_ids}

    # ------------------------------------------------------------------ #
    # Driver: get assigned route
    # ------------------------------------------------------------------ #

    def get_driver_route(self, db: Session, driver_id: int) -> dict:
        """Return the driver's most recently shared (pending/acknowledged/in_progress) route."""
        assignment = db.execute(
            select(RouteAssignment)
            .where(
                RouteAssignment.driver_id == driver_id,
                RouteAssignment.status.in_([
                    RouteAssignmentStatus.pending,
                    RouteAssignmentStatus.acknowledged,
                    RouteAssignmentStatus.in_progress,
                ]),
            )
            .order_by(RouteAssignment.shared_at.desc())
        ).scalars().first()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active route assignment found",
            )

        route: Route = db.execute(
            select(Route)
            .options(
                selectinload(Route.stops).selectinload(RouteStop.job),
                selectinload(Route.depot)
            )
            .where(Route.id == assignment.route_id)
        ).scalar_one()

        for stop in route.stops:
            if stop.stop_type and "depot" in stop.stop_type.lower():
                if route.depot:
                    stop.location = route.depot.location
                    if route.depot.address:
                        stop.address_formatted = route.depot.address.get("formatted", route.depot.name)
                    else:
                        stop.address_formatted = route.depot.name
            elif stop.job:
                stop.location = stop.job.location
                stop.address_formatted = stop.job.address_formatted

        return {
            "route": route,
            "assignment_status": assignment.status.value,
        }

    # ------------------------------------------------------------------ #
    # Driver: acknowledge route
    # ------------------------------------------------------------------ #

    def acknowledge_route(self, db: Session, driver_id: int) -> RouteAssignment:
        assignment = db.execute(
            select(RouteAssignment)
            .where(
                RouteAssignment.driver_id == driver_id,
                RouteAssignment.status == RouteAssignmentStatus.pending,
            )
            .order_by(RouteAssignment.shared_at.desc())
        ).scalars().first()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending route assignment to acknowledge",
            )

        assignment.status = RouteAssignmentStatus.acknowledged
        assignment.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assignment)
        return assignment

    # ------------------------------------------------------------------ #
    # Driver: update stop status (completed | failed)
    # ------------------------------------------------------------------ #

    def update_stop_status(
        self,
        db: Session,
        stop_id: int,
        driver_id: int,
        new_status: str,
    ) -> dict:
        if new_status not in ("completed", "failed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status must be 'completed' or 'failed'",
            )

        stop: RouteStop | None = db.get(RouteStop, stop_id)
        if not stop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop not found")

        # Validate the stop belongs to a route owned by this driver
        route: Route | None = db.get(Route, stop.route_id)
        if not route or route.driver_id != driver_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Stop does not belong to your route")

        now = datetime.now(timezone.utc)
        stop.actual_arrival_time = stop.actual_arrival_time or now
        stop.actual_departure_time = now

        # Mirror status onto the linked Job
        if stop.job_id:
            job: Job | None = db.get(Job, stop.job_id)
            if job:
                job.status = JobStatus.completed if new_status == "completed" else JobStatus.failed

        # Mark assignment as in_progress on first stop completion
        assignment = db.execute(
            select(RouteAssignment).where(
                RouteAssignment.route_id == route.id,
                RouteAssignment.driver_id == driver_id,
            )
        ).scalar_one_or_none()

        if assignment and assignment.status == RouteAssignmentStatus.acknowledged:
            assignment.status = RouteAssignmentStatus.in_progress

        db.commit()

        # Calculate updated progress for the WebSocket broadcast
        all_stops = db.execute(
            select(RouteStop).where(RouteStop.route_id == route.id, RouteStop.job_id.is_not(None))
        ).scalars().all()

        total = len(all_stops)
        attempted = sum(
            1 for s in all_stops if s.actual_departure_time is not None
        )
        progress = round((attempted / total * 100) if total else 0)

        driver: TeamMember | None = db.get(TeamMember, driver_id)

        return {
            "route_id": route.id,
            "stop_id": stop_id,
            "new_status": new_status,
            "driver_id": driver_id,
            "driver_name": driver.name if driver else "Unknown",
            "tenant_id": route.tenant_id,
            "progress_percentage": progress,
        }


route_sharing_service = RouteSharingService()
