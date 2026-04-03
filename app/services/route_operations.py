"""
Route Operations Service.

Per-driver route modifications on completed optimization results.
All operations modify the SAME optimization_request's JSONB result in-place.

Sync operations:
  - reverse_route: reorder stops, no VRP

Async operations (via RQ):
  - add_stop:       add job → VRP → update result.routes[i]
  - swap_driver:    change driver → VRP → update result.routes[i]
  - re_optimize:    VRP → update result.routes[i]
"""

import copy
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException, status

from app.core.logging_config import logger
from app.models.optimization_request import OptimizationRequest, OptimizationStatus
from app.models.job import Job, JobStatus
from app.models.team_member import TeamMember
from app.models.route import Route, RouteStop, RouteStatus
from app.crud.optimization_request import optimization_request as opt_crud
from app.schemas.route_operations import RouteOperationResponse


class RouteOperationsService:
    """
    Per-driver route operations.

    Async ops queue to RQ, update result.routes[i] in-place,
    then set status back to completed. Frontend polls using existing infra.
    """

    # ────────────────────────────────────
    # 1. ADD STOP
    # ────────────────────────────────────

    def add_stop(
        self,
        db: Session,
        optimization_request_id: int,
        route_index: int,
        job_id: int,
        tenant_id: int,
    ) -> RouteOperationResponse:
        """Add a job to a driver's route and re-optimize via RQ."""

        opt_request, result = self._load_and_validate(
            db, optimization_request_id, route_index, tenant_id
        )
        route_data = result["routes"][route_index]

        # Validate job
        job = db.query(Job).filter(
            Job.id == job_id, Job.tenant_id == tenant_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if job.status != JobStatus.draft:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} status is '{job.status}', must be 'draft'"
            )

        # Add job_id to the optimization_request's job_ids array
        current_job_ids = list(opt_request.job_ids or [])
        if job_id not in current_job_ids:
            current_job_ids.append(job_id)
            opt_request.job_ids = current_job_ids

        # Set status to processing so frontend polls
        opt_request.status = OptimizationStatus.PROCESSING
        opt_request.error_message = None
        db.add(opt_request)
        db.commit()

        # Queue RQ worker
        self._queue_route_operation(
            optimization_request_id=optimization_request_id,
            route_index=route_index,
            operation="add_stop",
            params={"job_id": job_id},
            tenant_id=tenant_id,
        )

        logger.info(
            f"add_stop: queued job {job_id} → route[{route_index}] "
            f"of opt {optimization_request_id}"
        )

        return RouteOperationResponse(
            success=True,
            message=f"Adding job #{job_id} to route. Re-optimizing...",
        )

    # ────────────────────────────────────
    # 2. SWAP DRIVER
    # ────────────────────────────────────

    def swap_driver(
        self,
        db: Session,
        optimization_request_id: int,
        route_index: int,
        new_driver_id: int,
        tenant_id: int,
    ) -> RouteOperationResponse:
        """Swap a route's driver and re-optimize via RQ."""

        opt_request, result = self._load_and_validate(
            db, optimization_request_id, route_index, tenant_id
        )

        # Validate new driver exists
        new_driver = db.query(TeamMember).filter(
            TeamMember.id == new_driver_id, TeamMember.tenant_id == tenant_id
        ).first()
        if not new_driver:
            raise HTTPException(status_code=404, detail=f"Driver {new_driver_id} not found")

        old_driver_name = result["routes"][route_index].get("team_member_name", "Unknown")

        # Update team_member_ids if the new driver isn't already in the list
        current_tm_ids = list(opt_request.team_member_ids or [])
        if new_driver_id not in current_tm_ids:
            current_tm_ids.append(new_driver_id)
            opt_request.team_member_ids = current_tm_ids

        # Set status to processing
        opt_request.status = OptimizationStatus.PROCESSING
        opt_request.error_message = None
        db.add(opt_request)
        db.commit()

        # Queue RQ worker
        self._queue_route_operation(
            optimization_request_id=optimization_request_id,
            route_index=route_index,
            operation="swap_driver",
            params={"new_driver_id": new_driver_id},
            tenant_id=tenant_id,
        )

        logger.info(
            f"swap_driver: route[{route_index}] of opt {optimization_request_id} "
            f"{old_driver_name} → {new_driver.name}"
        )

        return RouteOperationResponse(
            success=True,
            message=f"Swapping to {new_driver.name}. Re-optimizing...",
        )

    # ────────────────────────────────────
    # 3. REMOVE STOP
    # ────────────────────────────────────

    def remove_stop(
        self,
        db: Session,
        optimization_request_id: int,
        route_index: int,
        job_id: int,
        tenant_id: int,
    ) -> RouteOperationResponse:
        """Remove a job from a driver's route and re-optimize via RQ."""

        opt_request, result = self._load_and_validate(
            db, optimization_request_id, route_index, tenant_id
        )
        route_data = result["routes"][route_index]

        # Verify job is actually active in this route
        existing_job_ids = [
            s["job_id"] for s in route_data["stops"]
            if s.get("job_id") and s.get("stop_type") == "job"
        ]
        if job_id not in existing_job_ids:
            raise HTTPException(status_code=400, detail=f"Job {job_id} not found in this route")

        # Set status to processing so frontend polls
        opt_request.status = OptimizationStatus.PROCESSING
        opt_request.error_message = None
        db.add(opt_request)
        db.commit()

        # Queue RQ worker
        self._queue_route_operation(
            optimization_request_id=optimization_request_id,
            route_index=route_index,
            operation="remove_stop",
            params={"job_id": job_id},
            tenant_id=tenant_id,
        )

        logger.info(
            f"remove_stop: queued removal of job {job_id} from route[{route_index}] "
            f"of opt {optimization_request_id}"
        )

        return RouteOperationResponse(
            success=True,
            message=f"Removing job #{job_id} from route. Re-optimizing...",
        )

    # ────────────────────────────────────
    # 4. REVERSE ROUTE (synchronous)
    # ────────────────────────────────────

    def reverse_route(
        self,
        db: Session,
        optimization_request_id: int,
        route_index: int,
        tenant_id: int,
    ) -> RouteOperationResponse:
        """Reverse a route's stop order. Synchronous — no VRP needed."""

        opt_request, result = self._load_and_validate(
            db, optimization_request_id, route_index, tenant_id
        )
        route_data = result["routes"][route_index]
        stops = route_data["stops"]

        # Separate depot and job stops
        depot_stops = [s for s in stops if s.get("stop_type") == "depot"]
        job_stops = [s for s in stops if s.get("stop_type") == "job"]

        if len(job_stops) < 2:
            return RouteOperationResponse(
                success=True,
                message="Route has fewer than 2 stops — nothing to reverse.",
            )

        # Reverse only the job stops
        job_stops.reverse()

        # Rebuild: depot_start + reversed jobs + depot_end
        new_stops = []
        if depot_stops:
            new_stops.append(depot_stops[0])       # departure depot
        new_stops.extend(job_stops)
        if len(depot_stops) > 1:
            new_stops.append(depot_stops[-1])       # return depot

        # Update JSONB
        result["routes"][route_index]["stops"] = new_stops
        opt_request.result = result
        db.add(opt_request)

        # Update DB RouteStop sequence_order
        self._sync_route_stop_order(
            db, optimization_request_id,
            route_data["team_member_id"], new_stops, tenant_id
        )

        db.commit()
        db.refresh(opt_request)

        logger.info(f"reverse_route: route[{route_index}] of opt {optimization_request_id}")

        return RouteOperationResponse(
            success=True,
            message="Route reversed successfully.",
        )

    # ────────────────────────────────────
    # 4. RE-OPTIMIZE ROUTE
    # ────────────────────────────────────

    def re_optimize_route(
        self,
        db: Session,
        optimization_request_id: int,
        route_index: int,
        tenant_id: int,
    ) -> RouteOperationResponse:
        """Re-optimize a single driver's route via RQ."""

        opt_request, result = self._load_and_validate(
            db, optimization_request_id, route_index, tenant_id
        )
        route_data = result["routes"][route_index]
        job_ids = [
            s["job_id"] for s in route_data["stops"]
            if s.get("job_id") and s.get("stop_type") == "job"
        ]

        if not job_ids:
            raise HTTPException(status_code=400, detail="Route has no jobs to re-optimize")

        driver_name = route_data.get("team_member_name", "Unknown")

        # Set status to processing
        opt_request.status = OptimizationStatus.PROCESSING
        opt_request.error_message = None
        db.add(opt_request)
        db.commit()

        # Queue RQ worker
        self._queue_route_operation(
            optimization_request_id=optimization_request_id,
            route_index=route_index,
            operation="re_optimize",
            params={},
            tenant_id=tenant_id,
        )

        logger.info(
            f"re_optimize: route[{route_index}] of opt {optimization_request_id} "
            f"({len(job_ids)} jobs, driver {driver_name})"
        )

        return RouteOperationResponse(
            success=True,
            message=f"Re-optimizing {driver_name}'s route ({len(job_ids)} stops)...",
        )

    # ──────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────

    def _load_and_validate(
        self, db: Session, optimization_request_id: int, route_index: int, tenant_id: int
    ) -> Tuple[OptimizationRequest, dict]:
        """Load optimization request and validate route_index bounds."""

        opt_request = opt_crud.get(db=db, id=optimization_request_id, tenant_id=tenant_id)
        if not opt_request:
            raise HTTPException(status_code=404, detail="Optimization request not found")

        if opt_request.status != OptimizationStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot modify — optimization status is '{opt_request.status.value}'"
            )

        result = opt_request.result
        if not result or "routes" not in result:
            raise HTTPException(status_code=400, detail="Optimization has no routes")

        if route_index < 0 or route_index >= len(result["routes"]):
            raise HTTPException(
                status_code=400,
                detail=f"route_index {route_index} out of range [0, {len(result['routes']) - 1}]"
            )

        return opt_request, result

    def _queue_route_operation(
        self,
        optimization_request_id: int,
        route_index: int,
        operation: str,
        params: dict,
        tenant_id: int,
    ):
        """Submit a route operation to the RQ worker queue."""
        import redis
        from rq import Queue
        from app.core.config import settings
        from app.database import DATABASE_URL

        redis_conn = redis.from_url(settings.REDIS_URL)
        queue = Queue(settings.OPTIMIZATION_QUEUE_NAME, connection=redis_conn)

        queue.enqueue(
            run_route_operation_worker,
            optimization_request_id=optimization_request_id,
            route_index=route_index,
            operation=operation,
            params=params,
            tenant_id=tenant_id,
            database_url=DATABASE_URL,
            job_timeout="5m",
        )

    def _sync_route_stop_order(
        self,
        db: Session,
        optimization_request_id: int,
        team_member_id: int,
        new_stops: list,
        tenant_id: int,
    ):
        """Update RouteStop sequence_order in DB to match new JSONB order."""

        route = db.query(Route).filter(
            Route.optimization_request_id == optimization_request_id,
            Route.driver_id == team_member_id,
            Route.tenant_id == tenant_id,
        ).first()

        if not route:
            logger.warning(f"No Route row for opt {optimization_request_id}, driver {team_member_id}")
            return

        job_stops_map = {
            stop.job_id: stop for stop in route.stops
            if stop.stop_type == "job" and stop.job_id
        }

        seq = 1
        for s in new_stops:
            if s.get("stop_type") == "job" and s.get("job_id"):
                rs = job_stops_map.get(s["job_id"])
                if rs:
                    rs.sequence_order = seq
                    seq += 1


# Singleton
route_operations_service = RouteOperationsService()


# ═══════════════════════════════════════════════════════════════
# RQ WORKER — runs in separate process
# ═══════════════════════════════════════════════════════════════

def run_route_operation_worker(
    optimization_request_id: int,
    route_index: int,
    operation: str,
    params: dict,
    tenant_id: int,
    database_url: str,
):
    """
    RQ worker for per-route VRP operations.

    Runs in a separate process. Creates its own DB session.
    1. Loads the optimization request
    2. Extracts target route's job_ids + driver
    3. Runs VRP pipeline for 1 driver + N jobs
    4. Replaces result.routes[route_index] with new VRP output
    5. Updates DB Route/RouteStop records
    6. Sets status back to 'completed'
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Import models
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.depot import Depot
    from app.models.vehicle import Vehicle
    from app.models.team_member import TeamMember
    from app.models.job import Job, JobStatus
    from app.models.route import Route, RouteStop, RouteStatus
    from app.models.optimization_request import OptimizationRequest, OptimizationStatus
    from app.crud.optimization_request import optimization_request as opt_crud
    from app.crud.route import route as route_crud
    from app.crud.job import job as job_crud

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        logger.info(
            f"Route operation worker started: opt={optimization_request_id}, "
            f"route_index={route_index}, operation={operation}, params={params}"
        )

        # 1. Load optimization request
        opt_request = opt_crud.get(db=db, id=optimization_request_id, tenant_id=tenant_id)
        if not opt_request:
            raise Exception(f"Optimization request {optimization_request_id} not found")

        result = opt_request.result
        if not result or route_index >= len(result.get("routes", [])):
            raise Exception(f"Invalid route_index {route_index}")

        route_data = result["routes"][route_index]

        # 2. Determine job_ids and driver_id for this route
        existing_job_ids = [
            s["job_id"] for s in route_data["stops"]
            if s.get("job_id") and s.get("stop_type") == "job"
        ]
        driver_id = route_data["team_member_id"]

        if operation == "add_stop":
            new_job_id = params["job_id"]
            job_ids = existing_job_ids + [new_job_id]
        elif operation == "remove_stop":
            remove_job_id = params["job_id"]
            job_ids = [jid for jid in existing_job_ids if jid != remove_job_id]
            # Also reset the target job to draft status immediately (before VRP)
            # so it becomes unassigned.
            job = db.query(Job).filter(Job.id == remove_job_id, Job.tenant_id == tenant_id).first()
            if job and job.status == JobStatus.assigned:
                job.status = JobStatus.draft
                job.route_id = None
                job.assigned_to = None
                # Let DB flush handle this during next step
        elif operation == "swap_driver":
            driver_id = params["new_driver_id"]
            job_ids = existing_job_ids
        elif operation == "re_optimize":
            job_ids = existing_job_ids
        else:
            raise Exception(f"Unknown operation: {operation}")

        if not job_ids:
            raise Exception("No jobs to optimize")

        # 3. Reset target jobs to draft so VRP can assign them
        for jid in job_ids:
            job = db.query(Job).filter(Job.id == jid, Job.tenant_id == tenant_id).first()
            if job and job.status == JobStatus.assigned:
                job.status = JobStatus.draft
                job.route_id = None
                job.assigned_to = None
        db.flush()

        # 4. Run VRP pipeline
        from app.services.optimization_engine.data_loader import OptimizationDataLoader
        from app.services.optimization_engine.routing_client import get_routing_client
        from app.services.optimization_engine.solver import VRPSolver
        from app.services.optimization_engine.result_formatter import ResultFormatter
        from app.services.optimization_engine.route_storage import RouteStorage

        logger.info(f"Loading data for 1 driver ({driver_id}), {len(job_ids)} jobs")
        data_loader = OptimizationDataLoader(db)
        data = data_loader.load(
            depot_id=opt_request.depot_id,
            job_ids=job_ids,
            team_member_ids=[driver_id],
            scheduled_date=opt_request.scheduled_date,
            tenant_id=tenant_id,
        )

        # Distance/duration matrix
        routing_client = get_routing_client()
        all_coords = data.get_all_location_coords()
        depot_coords = all_coords[0]
        all_destinations = all_coords[1:]

        vehicle_type = "car"
        if data.team_members and data.team_members[0].vehicle_id:
            vehicle = data.vehicles.get(data.team_members[0].vehicle_id)
            if vehicle and vehicle.type:
                vehicle_type = vehicle.type.value

        matrix = routing_client.get_matrix_for_optimization(
            depot_location=depot_coords,
            job_locations=all_destinations,
            vehicle_type=vehicle_type,
        )

        # Solve VRP
        num_jobs = len(data.jobs)
        time_limit = 2 if num_jobs <= 10 else 30 if num_jobs <= 40 else 90

        logger.info(f"Solving VRP: {num_jobs} jobs, time_limit={time_limit}s")
        solver = VRPSolver(
            data=data,
            distance_matrix=matrix["distances"],
            duration_matrix=matrix["durations"],
            optimization_goal=opt_request.optimization_goal,
        )
        solution = solver.solve(time_limit_seconds=time_limit)
        if not solution:
            raise Exception("VRP solver found no feasible solution")

        # Format result
        formatter = ResultFormatter(data)
        new_result_data = formatter.format(solution)

        # 5. We now have new_result_data with 1 route.
        #    Replace result.routes[route_index] with it.
        if not new_result_data.get("routes"):
            raise Exception("VRP produced no routes")

        new_route = new_result_data["routes"][0]  # 1 driver → 1 route

        # Deep-copy the old result and splice in the new route
        updated_result = copy.deepcopy(result)
        updated_result["routes"][route_index] = new_route

        # Recalculate totals across all routes
        total_dist = sum(r.get("total_distance_meters", 0) for r in updated_result["routes"])
        total_dur = sum(r.get("total_duration_seconds", 0) for r in updated_result["routes"])
        updated_result["total_distance_meters"] = total_dist
        updated_result["total_duration_seconds"] = total_dur

        # Handle unassigned from this sub-problem — add back to the parent
        new_unassigned = new_result_data.get("unassigned_jobs", [])
        if new_unassigned:
            # Remove any previous unassigned for these job_ids, then add new ones
            existing_unassigned = [
                u for u in updated_result.get("unassigned_jobs", [])
                if u["job_id"] not in job_ids
            ]
            updated_result["unassigned_jobs"] = existing_unassigned + new_unassigned

        # 6. Delete old Route + RouteStop DB records for this driver
        old_driver_id = route_data["team_member_id"]  # may differ from new driver_id for swap
        old_route = db.query(Route).filter(
            Route.optimization_request_id == optimization_request_id,
            Route.driver_id == old_driver_id,
            Route.tenant_id == tenant_id,
        ).first()

        if old_route:
            db.query(RouteStop).filter(RouteStop.route_id == old_route.id).delete(
                synchronize_session=False
            )
            db.delete(old_route)
            db.flush()

        # 7. Create new Route + RouteStop from the VRP result
        route_storage = RouteStorage(db, data)
        route_storage.store_routes(
            optimization_request_id=optimization_request_id,
            formatted_result=new_result_data,  # has 1 route
            tenant_id=tenant_id,
        )

        # 8. Persist updated JSONB result + set status back to completed
        opt_request.result = updated_result
        opt_request.status = OptimizationStatus.COMPLETED
        opt_request.error_message = None
        db.add(opt_request)
        db.commit()

        logger.info(
            f"Route operation completed: opt={optimization_request_id}, "
            f"route_index={route_index}, operation={operation}"
        )

    except Exception as e:
        logger.error(
            f"Route operation failed: opt={optimization_request_id}, "
            f"operation={operation}: {str(e)}"
        )
        logger.error(traceback.format_exc())

        # Set status back to completed (with error) so UI doesn't get stuck
        try:
            opt_request = opt_crud.get(db=db, id=optimization_request_id, tenant_id=tenant_id)
            if opt_request:
                opt_request.status = OptimizationStatus.COMPLETED
                opt_request.error_message = f"Route operation failed: {str(e)}"
                db.add(opt_request)
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Failed to rollback status: {rollback_err}")

    finally:
        db.close()
        engine.dispose()
