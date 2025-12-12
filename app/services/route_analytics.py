from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any

from app.models.optimization_request import OptimizationRequest, OptimizationStatus
from app.models.route import Route, RouteStop
from app.models.job import Job, JobStatus
from app.models.team_member import TeamMember
from app.schemas.route import RouteAnalyticsItem, TeamMemberSummary

class RouteAnalyticsService:
    def get_all_routes_analytics(self, db: Session, tenant_id: int) -> List[RouteAnalyticsItem]:
        """
        Fetch aggregated analytics for all optimized routes (OptimizationRequests).
        """
        # Fetch optimization requests with related data
        # Using joinedload to prevent N+1 queries
        requests = (
            db.query(OptimizationRequest)
            .filter(OptimizationRequest.tenant_id == tenant_id)
            .order_by(OptimizationRequest.created_at.desc())
            # Load routes and their drivers
            # Note: We need to define relationships in models if not already present
            # Assuming relationships exist or we fetch manually if needed.
            # OptimizationRequest doesn't have explicit relationship to Route yet based on model file I saw.
            # I will check models/optimization_request.py again. 
            # If relationship missing, I'll fetch manually for now or use implicit join.
        ).all()
        
        # OptimizationRequest model I saw didn't have 'routes' relationship defined.
        # I should fetch routes separately or add relationship.
        # For now, to adhere to "code modularity", I will fetch routes for each request.
        # Since number of plans isn't huge, this is acceptable. 
        # Better: Fetch all routes for these requests in one go.
        
        request_ids = [r.id for r in requests]
        
        # Fetch routes
        routes = (
            db.query(Route)
            .options(
                joinedload(Route.stops).joinedload(RouteStop.job)
            )
            .filter(Route.optimization_request_id.in_(request_ids))
            .all()
        )
        
        # Group routes by request ID
        routes_by_request: Dict[int, List[Route]] = {}
        for route in routes:
            if route.optimization_request_id not in routes_by_request:
                routes_by_request[route.optimization_request_id] = []
            routes_by_request[route.optimization_request_id].append(route)

        # Get all driver IDs to fetch team members in bulk
        driver_ids = set()
        for route in routes:
            if route.driver_id:
                driver_ids.add(route.driver_id)
        
        team_members = db.query(TeamMember).filter(TeamMember.id.in_(driver_ids)).all()
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
            status = "Scheduled"
            if req.status != OptimizationStatus.COMPLETED:
                # If optimization itself failed or is processing
                if req.status == OptimizationStatus.FAILED:
                    status = "Failed"
                elif req.status in [OptimizationStatus.PROCESSING, OptimizationStatus.QUEUED]:
                    status = "Processing"
            else:
                # Optimization done, check execution status
                if total_stops == 0:
                     status = "Empty"
                elif all_completed and total_stops > 0:
                    status = "Completed"
                elif has_in_transit or completed_stops > 0:
                    status = "In Progress"
                else:
                    status = "Scheduled"

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
