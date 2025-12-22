from sqlalchemy.orm import Session
from typing import List, Dict, Optional

from app.models.job import JobStatus
from app.models.optimization_request import OptimizationStatus
from app.models.route import RouteStatus
from app.schemas.route import RouteAnalyticsItem, TeamMemberSummary
from app.crud.optimization_request import optimization_request as optimization_request_crud
from app.crud.team_member import team_member as team_member_crud


class RouteAnalyticsService:
    def get_all_routes_analytics(self, db: Session, tenant_id: int, status_filter: Optional[RouteStatus] = None) -> List[RouteAnalyticsItem]:
        """
        Fetch aggregated analytics for all optimized routes (OptimizationRequests).
        """
        # Fetch optimization requests with routes using CRUD
        requests, routes = optimization_request_crud.get_with_routes(db=db, tenant_id=tenant_id)
        
        if not requests:
            return []
        
        # Group routes by request ID
        routes_by_request: Dict[int, list] = {}
        for route in routes:
            if route.optimization_request_id not in routes_by_request:
                routes_by_request[route.optimization_request_id] = []
            routes_by_request[route.optimization_request_id].append(route)

        # Get all driver IDs to fetch team members in bulk
        driver_ids = set()
        for route in routes:
            if route.driver_id:
                driver_ids.add(route.driver_id)
        
        # Fetch team members using CRUD
        team_members = team_member_crud.get_multi_by_ids(db=db, ids=list(driver_ids), tenant_id=tenant_id)
        team_member_map = {tm.id: tm for tm in team_members}

        analytics_items = []

        for req in requests:
            req_routes = routes_by_request.get(req.id, [])
            
            # 1. Metrics Aggregation
            total_distance = sum(r.total_distance_meters or 0 for r in req_routes)
            total_time = sum(r.total_duration_seconds or 0 for r in req_routes)
            
            # 2. Team Members
            assigned_members = []
            seen_drivers = set()
            for r in req_routes:
                if r.driver_id and r.driver_id not in seen_drivers and r.driver_id in team_member_map:
                    driver = team_member_map[r.driver_id]
                    assigned_members.append(TeamMemberSummary(
                        id=driver.id,
                        name=driver.name,
                        avatar_url=None
                    ))
                    seen_drivers.add(r.driver_id)

            # 3. Stop/Job Counts & Progress
            total_stops = 0
            completed_stops = 0
            failed_stops = 0  # Placeholder: JobStatus doesn't have 'failed' yet
            attempted_stops = 0
            
            has_in_transit = False
            all_completed = True
            
            for r in req_routes:
                for stop in r.stops:
                    if stop.stop_type == 'job':
                        total_stops += 1
                        job = stop.job
                        if job:
                            if job.status == JobStatus.completed:
                                completed_stops += 1
                                attempted_stops += 1
                            elif job.status == JobStatus.in_transit:
                                has_in_transit = True
                                all_completed = False
                                attempted_stops += 1
                            else:
                                all_completed = False

            progress_percentage = 0
            if total_stops > 0:
                progress_percentage = int((completed_stops / total_stops) * 100)
            
            # 4. Status Determination
            status = RouteStatus.scheduled.value
            if req.status != OptimizationStatus.COMPLETED:
                # If optimization itself failed or is processing
                if req.status == OptimizationStatus.FAILED:
                    status = RouteStatus.failed.value
                elif req.status in [OptimizationStatus.PROCESSING, OptimizationStatus.QUEUED]:
                    status = RouteStatus.processing.value
            else:
                # Optimization done, check execution status
                if total_stops == 0:
                    status = RouteStatus.completed.value
                elif all_completed and total_stops > 0:
                    status = RouteStatus.completed.value
                elif has_in_transit or completed_stops > 0:
                    status = RouteStatus.in_transit.value
                else:
                    status = RouteStatus.scheduled.value

            if status_filter and status != status_filter.value:
                continue

            analytics_items.append(RouteAnalyticsItem(
                id=req.id,
                optimization_id=req.id,
                name=req.route_name,
                status=status,
                total_distance=total_distance,
                total_time=total_time,
                progress_percentage=progress_percentage,
                total_stops=total_stops,
                completed_stops=completed_stops,
                failed_stops=failed_stops,
                attempted_stops=attempted_stops,
                assigned_team_members=assigned_members,
                rating=None, # Placeholder
                scheduled_date=req.scheduled_date,
                created_at=req.created_at
            ))
            
        return analytics_items


route_analytics_service = RouteAnalyticsService()
