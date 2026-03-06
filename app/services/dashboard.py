from sqlalchemy.orm import Session
from app.crud.dashboard import dashboard as dashboard_crud
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardKPI,
    OptimizationImpact,
    RecentRoute,
    TopDriver,
    UpcomingDay,
)
from app.core.logging_config import logger
from app.services.route_analytics import route_analytics_service


class DashboardService:
    """Service layer for dashboard business logic."""

    def __init__(self):
        self.crud = dashboard_crud

    def get_dashboard(self, db: Session, tenant_id: int) -> DashboardResponse:
        """
        Get aggregated dashboard data for a tenant.

        Coordinates CRUD calls and transforms raw data into response schemas.
        """
        try:
            kpi = self._build_kpi(db, tenant_id)
            optimization_impact = self._build_optimization_impact(db, tenant_id)
            recent_routes = self._build_recent_routes(db, tenant_id)
            top_drivers = self._build_top_drivers(db, tenant_id)
            upcoming = self._build_upcoming(db, tenant_id)

            return DashboardResponse(
                kpi=kpi,
                optimization_impact=optimization_impact,
                recent_routes=recent_routes,
                top_drivers=top_drivers,
                upcoming=upcoming,
            )
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {type(e).__name__}: {str(e)}")
            raise

    def _build_kpi(self, db: Session, tenant_id: int) -> DashboardKPI:
        """Build KPI response from CRUD data."""
        job_counts = self.crud.get_job_counts(db, tenant_id)
        active_routes = self.crud.get_active_routes_count(db, tenant_id)
        total_drivers = self.crud.get_drivers_count(db, tenant_id)
        total_depots = self.crud.get_depots_count(db, tenant_id)

        return DashboardKPI(
            total_jobs=job_counts["total"],
            active_routes=active_routes,
            completed_jobs=job_counts["completed"],
            scheduled_jobs=job_counts["scheduled"],
            total_drivers=total_drivers,
            total_depots=total_depots,
        )

    def _build_optimization_impact(self, db: Session, tenant_id: int) -> OptimizationImpact:
        """Build optimization impact response, converting units."""
        savings = self.crud.get_optimization_savings(db, tenant_id)

        return OptimizationImpact(
            total_distance_saved_km=round(savings["distance_saved_meters"] / 1000, 1),
            total_time_saved_hours=round(savings["time_saved_seconds"] / 3600, 1),
            vehicles_saved=savings["vehicles_saved"],
        )

    def _build_recent_routes(self, db: Session, tenant_id: int) -> list[RecentRoute]:
        """Build recent routes response using efficient database query."""
        from app.models.route import RouteStatus
        rows = self.crud.get_recent_routes(db, tenant_id, limit=5)

        # Map to RecentRoute. We calculate the status dynamically 
        # based on stops completed since we don't eager load the whole tree.
        recent = []
        for row in rows:
            # row.status may be a RouteStatus enum OR a plain string (from SQL CASE expression).
            # Normalise to a plain string either way.
            raw_status = row.status.value if hasattr(row.status, "value") else (row.status or "scheduled")

            # If the route is scheduled but some jobs are already done → promote to in_transit.
            # The completed case is already handled by the SQL CASE in get_recent_routes.
            if raw_status == RouteStatus.scheduled.value and row.completed_stops > 0:
                raw_status = RouteStatus.in_transit.value
                
            recent.append(
                RecentRoute(
                    key=str(row.optimization_request_id),
                    name=row.name or f"Route #{row.id}",
                    driver=row.driver_name or "Unassigned",
                    stops=row.total_stops or 0,
                    completed=row.completed_stops or 0,
                    status=raw_status,
                )
            )

        return recent

    def _build_top_drivers(self, db: Session, tenant_id: int) -> list[TopDriver]:
        """Build top drivers response, computing rates from raw counts."""
        rows = self.crud.get_top_drivers(db, tenant_id)

        return [
            TopDriver(
                name=row.name,
                completion_rate=round(
                    (row.total_completed / row.total_assigned * 100) if row.total_assigned > 0 else 0, 1
                ),
                on_time_rate=round(
                    (row.on_time_stops / row.arrived_stops * 100) if row.arrived_stops > 0 else 0, 1
                ),
            )
            for row in rows
        ]

    def _build_upcoming(self, db: Session, tenant_id: int) -> list[UpcomingDay]:
        """Build upcoming schedule response, formatting dates."""
        rows = self.crud.get_upcoming_schedule(db, tenant_id)

        return [
            UpcomingDay(
                date=row.sdate.strftime("%b %d") if row.sdate else "",
                jobs=row.jobs,
                routes=row.routes,
            )
            for row in rows
        ]


# Singleton instance
dashboard_service = DashboardService()
