from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, select, and_
from app.models.job import Job, JobStatus
from app.models.route import Route, RouteStop, RouteStatus
from app.models.team_member import TeamMember, TeamMemberRole
from app.models.depot import Depot
from app.models.optimization_request import OptimizationRequest, OptimizationStatus


class CRUDDashboard:
    """CRUD operations for dashboard aggregation queries."""

    def get_job_counts(self, db: Session, tenant_id: int) -> dict:
        """
        Get job counts by status for a tenant.

        Returns:
            Dict with total, completed, scheduled counts
        """
        row = db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Job.status == JobStatus.completed).label("completed"),
                func.count().filter(Job.status == JobStatus.assigned).label("scheduled"),
            ).where(Job.tenant_id == tenant_id)
        ).one()

        return {
            "total": row.total or 0,
            "completed": row.completed or 0,
            "scheduled": row.scheduled or 0,
        }

    def get_active_routes_count(self, db: Session, tenant_id: int) -> int:
        """
        Get count of active routes (optimization requests) currently in transit.
        Matches logic in RouteAnalyticsService exactly, but done via SQL.
        """
        # A route is "in_transit" if:
        # 1. Optimization is COMPLETED
        # 2. It has > 0 stops
        # 3. Not all jobs are completed (or 0 attempted)
        # 4. It has at least one job in_transit OR at least one job completed.
        # So we count the number of such requests.
        
        from sqlalchemy import cast, String

        # Subquery to calculate stop metrics per request.
        # total_stops counts stops WITH a linked job (Job.id IS NOT NULL after outer join).
        # func.count(Job.id) naturally excludes NULLs, so stops with no linked job_id are ignored —
        # matching route_analytics_service's `if job:` guard exactly.
        # We do NOT additionally filter by stop_type to keep it consistent with
        # completed_jobs and in_transit_jobs (which also don't filter stop_type).
        stop_metrics = (
            select(
                Route.optimization_request_id.label("req_id"),
                func.count(Job.id).label("total_stops"),
                func.count(Job.id).filter(cast(Job.status, String) == JobStatus.completed.value).label("completed_jobs"),
                func.count(Job.id).filter(cast(Job.status, String) == JobStatus.in_transit.value).label("in_transit_jobs"),
            )
            .select_from(Route)
            .outerjoin(RouteStop, Route.id == RouteStop.route_id)
            .outerjoin(Job, RouteStop.job_id == Job.id)
            .where(Route.tenant_id == tenant_id)
            .group_by(Route.optimization_request_id)
            .subquery()
        )

        # Count requests that meet the "in_transit" criteria
        stmt = (
            select(func.count(OptimizationRequest.id))
            .outerjoin(stop_metrics, OptimizationRequest.id == stop_metrics.c.req_id)
            .where(
                and_(
                    OptimizationRequest.tenant_id == tenant_id,
                    OptimizationRequest.status == OptimizationStatus.COMPLETED,
                    func.coalesce(stop_metrics.c.total_stops, 0) > 0,
                    # not all completed
                    func.coalesce(stop_metrics.c.completed_jobs, 0) < func.coalesce(stop_metrics.c.total_stops, 0),
                    # has in_transit OR has completed
                    (func.coalesce(stop_metrics.c.in_transit_jobs, 0) > 0) | (func.coalesce(stop_metrics.c.completed_jobs, 0) > 0)
                )
            )
        )

        count = db.execute(stmt).scalar()
        return count or 0

    def get_drivers_count(self, db: Session, tenant_id: int) -> int:
        """Get count of team members with driver role."""
        return db.execute(
            select(func.count()).where(
                TeamMember.tenant_id == tenant_id,
                TeamMember.role_type == TeamMemberRole.driver,
            )
        ).scalar() or 0

    def get_depots_count(self, db: Session, tenant_id: int) -> int:
        """Get count of depots for a tenant."""
        return db.execute(
            select(func.count()).where(Depot.tenant_id == tenant_id)
        ).scalar() or 0

    def get_optimization_savings(self, db: Session, tenant_id: int) -> dict:
        """
        Get aggregated optimization savings from routes.

        Returns:
            Dict with distance_saved_meters, time_saved_seconds, vehicles_saved
        """
        row = db.execute(
            select(
                func.coalesce(func.sum(Route.total_distance_saved_meters), 0).label("distance_saved"),
                func.coalesce(func.sum(Route.total_time_saved_seconds), 0).label("time_saved"),
            ).where(Route.tenant_id == tenant_id)
        ).one()

        vehicles_saved = db.execute(
            select(func.count()).where(
                Route.tenant_id == tenant_id,
                Route.total_distance_saved_meters > 0,
            )
        ).scalar() or 0

        return {
            "distance_saved_meters": float(row.distance_saved),
            "time_saved_seconds": float(row.time_saved),
            "vehicles_saved": vehicles_saved,
        }

    def get_recent_routes(self, db: Session, tenant_id: int, limit: int = 5) -> list:
        """
        Get the most recent routes with driver name and stop progress.

        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            limit: Maximum number of routes to return

        Returns:
            List of row tuples with id, name, driver_name, total_stops, completed_stops, status
        """
        # completed_stops counts jobs with status=completed (matches route_analytics_service)
        # NOT actual_arrival_time, to avoid divergence where arrival is set but job not completed
        from sqlalchemy import cast, String
        stop_counts = (
            select(
                RouteStop.route_id,
                func.count(Job.id).filter(RouteStop.stop_type == "job").label("total_stops"),
                func.count(Job.id).filter(
                    and_(
                        RouteStop.stop_type == "job",
                        cast(Job.status, String) == JobStatus.completed.value,
                    )
                ).label("completed_stops"),
            )
            .outerjoin(Job, RouteStop.job_id == Job.id)
            .group_by(RouteStop.route_id)
            .subquery()
        )

        stmt = (
            select(
                Route.id,
                OptimizationRequest.route_name.label("name"),
                TeamMember.name.label("driver_name"),
                func.coalesce(stop_counts.c.total_stops, 0).label("total_stops"),
                func.coalesce(stop_counts.c.completed_stops, 0).label("completed_stops"),
                Route.status,
            )
            .outerjoin(OptimizationRequest, Route.optimization_request_id == OptimizationRequest.id)
            .outerjoin(TeamMember, Route.driver_id == TeamMember.id)
            .outerjoin(stop_counts, Route.id == stop_counts.c.route_id)
            .where(Route.tenant_id == tenant_id)
            .order_by(Route.created_at.desc(), Route.id.desc())
            .limit(limit)
        )

        return db.execute(stmt).all()

    def get_top_drivers(self, db: Session, tenant_id: int, limit: int = 3) -> list:
        """
        Get top drivers by job completion rate.

        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            limit: Maximum number of drivers to return

        Returns:
            List of row tuples with name, total_assigned, total_completed, arrived_stops, on_time_stops
        """
        driver_job_stats = (
            select(
                Job.assigned_to.label("driver_id"),
                func.count().label("total_assigned"),
                func.count().filter(Job.status == JobStatus.completed).label("total_completed"),
            )
            .where(
                Job.tenant_id == tenant_id,
                Job.assigned_to.isnot(None),
            )
            .group_by(Job.assigned_to)
            .subquery()
        )

        on_time_stats = (
            select(
                Route.driver_id,
                func.count().filter(RouteStop.actual_arrival_time.isnot(None)).label("arrived_stops"),
                func.count().filter(
                    and_(
                        RouteStop.actual_arrival_time.isnot(None),
                        RouteStop.planned_arrival_time.isnot(None),
                        RouteStop.actual_arrival_time <= RouteStop.planned_arrival_time,
                    )
                ).label("on_time_stops"),
            )
            .join(Route, RouteStop.route_id == Route.id)
            .where(Route.tenant_id == tenant_id)
            .group_by(Route.driver_id)
            .subquery()
        )

        stmt = (
            select(
                TeamMember.name,
                func.coalesce(driver_job_stats.c.total_assigned, 0).label("total_assigned"),
                func.coalesce(driver_job_stats.c.total_completed, 0).label("total_completed"),
                func.coalesce(on_time_stats.c.arrived_stops, 0).label("arrived_stops"),
                func.coalesce(on_time_stats.c.on_time_stops, 0).label("on_time_stops"),
            )
            .outerjoin(driver_job_stats, TeamMember.id == driver_job_stats.c.driver_id)
            .outerjoin(on_time_stats, TeamMember.id == on_time_stats.c.driver_id)
            .where(
                TeamMember.tenant_id == tenant_id,
                TeamMember.role_type == TeamMemberRole.driver,
            )
            .group_by(
                TeamMember.id,
                TeamMember.name,
                driver_job_stats.c.total_assigned,
                driver_job_stats.c.total_completed,
                on_time_stats.c.arrived_stops,
                on_time_stats.c.on_time_stops,
            )
            .having(func.coalesce(driver_job_stats.c.total_assigned, 0) > 0)
            .order_by(
                (
                    func.coalesce(driver_job_stats.c.total_completed, 0) * 100
                    / func.greatest(func.coalesce(driver_job_stats.c.total_assigned, 0), 1)
                ).desc(),
                TeamMember.name.asc(),
            )
            .limit(limit)
        )

        return db.execute(stmt).all()

    def get_upcoming_schedule(self, db: Session, tenant_id: int, limit: int = 3) -> list:
        """
        Get upcoming days with scheduled jobs and routes.

        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            limit: Maximum number of upcoming days to return

        Returns:
            List of row tuples with sdate, jobs, routes
        """
        today = date.today()

        job_counts = (
            select(
                Job.scheduled_date.label("sdate"),
                func.count().label("job_count"),
            )
            .where(
                Job.tenant_id == tenant_id,
                Job.scheduled_date > today,
            )
            .group_by(Job.scheduled_date)
            .subquery()
        )

        # Use Route.scheduled_date as primary, falling back to OptimizationRequest.scheduled_date.
        # This ensures standalone routes (without optimization_request) are also included.
        route_counts = (
            select(
                func.coalesce(Route.scheduled_date, OptimizationRequest.scheduled_date).label("sdate"),
                func.count().label("route_count"),
            )
            .select_from(Route)
            .outerjoin(OptimizationRequest, Route.optimization_request_id == OptimizationRequest.id)
            .where(
                Route.tenant_id == tenant_id,
                func.coalesce(Route.scheduled_date, OptimizationRequest.scheduled_date) >= today,
            )
            .group_by(func.coalesce(Route.scheduled_date, OptimizationRequest.scheduled_date))
            .subquery()
        )

        stmt = (
            select(
                func.coalesce(job_counts.c.sdate, route_counts.c.sdate).label("sdate"),
                func.coalesce(job_counts.c.job_count, 0).label("jobs"),
                func.coalesce(route_counts.c.route_count, 0).label("routes"),
            )
            .select_from(
                job_counts.outerjoin(route_counts, job_counts.c.sdate == route_counts.c.sdate, full=True)
            )
            .order_by("sdate")
            .limit(limit)
        )

        return db.execute(stmt).all()


# Singleton instance
dashboard = CRUDDashboard()
