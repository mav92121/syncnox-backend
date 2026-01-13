from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from datetime import date, datetime, time, timedelta

from app.models.route import Route, RouteStop
from app.models.team_member import TeamMember, TeamMemberRole
from app.schemas.schedule import (
    ScheduleResponse, 
    ResourceSchedule, 
    ScheduleBlock, 
    ScheduleBlockType,
    ScheduleBlockMetadata
)
from app.crud.team_member import team_member as team_member_crud


class ScheduleService:
    """
    Service for aggregating schedule data from routes and breaks.
    Designed to be extensible for future schedule types (employee shifts, etc.)
    """
    
    def get_driver_schedules(
        self,
        db: Session,
        tenant_id: int,
        schedule_date: date
    ) -> ScheduleResponse:
        """
        Get all driver schedules for a given date.
        
        Aggregates:
        - Route blocks (from Route/RouteStop tables)
        - Break blocks (from TeamMember static break times)
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            schedule_date: Date to fetch schedules for
            
        Returns:
            ScheduleResponse with all driver schedules
        """
        # 1. Fetch all drivers (team members with role=driver)
        drivers = team_member_crud.get_multi(db=db, tenant_id=tenant_id)
        drivers = [d for d in drivers if d.role_type == TeamMemberRole.driver]
        
        # 2. Fetch all routes for the date with their stops
        routes_with_stops = self._get_routes_for_date(db, tenant_id, schedule_date)
        
        # 3. Group routes by driver_id
        routes_by_driver = {}
        for route in routes_with_stops:
            if route.driver_id:
                if route.driver_id not in routes_by_driver:
                    routes_by_driver[route.driver_id] = []
                routes_by_driver[route.driver_id].append(route)
        
        # 4. Build resource schedules
        resource_schedules = []
        for driver in drivers:
            blocks = []
            
            # Add route blocks
            driver_routes = routes_by_driver.get(driver.id, [])
            for route in driver_routes:
                route_block = self._create_route_block(route, schedule_date)
                if route_block:
                    blocks.append(route_block)
                
                # Add break block from optimization result if available
                break_block = self._create_optimized_break_block(route)
                if break_block:
                    blocks.append(break_block)
                
                # Add idle blocks from optimization result
                idle_blocks = self._create_idle_blocks(route)
                blocks.extend(idle_blocks)
            
            # Fallback: Add static break block if no routes have break_info
            has_optimized_break = any(
                b.type == ScheduleBlockType.break_time for b in blocks
            )
            if not has_optimized_break:
                static_break = self._create_static_break_block(driver, schedule_date)
                if static_break:
                    blocks.append(static_break)
            
            # Sort blocks by start time
            blocks.sort(key=lambda b: b.start_time)
            
            resource_schedules.append(ResourceSchedule(
                resource_id=driver.id,
                resource_name=driver.name,
                resource_type="driver",
                blocks=blocks
            ))
        
        return ScheduleResponse(
            date=schedule_date,
            resources=resource_schedules
        )
    
    def _get_routes_for_date(
        self,
        db: Session,
        tenant_id: int,
        schedule_date: date
    ) -> List[Route]:
        """
        Fetch all routes for a specific date, eagerly loading stops.
        Filters by either Route.scheduled_date OR the linked OptimizationRequest.scheduled_date
        since Route.scheduled_date may be NULL for older routes.
        """
        from app.models.optimization_request import OptimizationRequest
        from sqlalchemy import or_
        from sqlalchemy.orm import selectinload
        
        stmt = (
            select(Route)
            .options(selectinload(Route.stops))  # Eager load stops in batch
            .outerjoin(OptimizationRequest, Route.optimization_request_id == OptimizationRequest.id)
            .where(
                Route.tenant_id == tenant_id,
                or_(
                    Route.scheduled_date == schedule_date,
                    OptimizationRequest.scheduled_date == schedule_date
                )
            )
        )
        
        return list(db.execute(stmt).scalars().all())
    
    def _create_route_block(
        self,
        route: Route,
        schedule_date: date
    ) -> Optional[ScheduleBlock]:
        """
        Create a schedule block from a route.
        Uses optimization result data for timing (depot start -> depot end).
        """
        # Get route name from optimization request
        route_name = "Route"
        opt_req = route.optimization_request
        if opt_req:
            route_name = opt_req.route_name or f"Route #{route.id}"
        
        # Try to get timing from optimization result JSON first (most accurate)
        start_time = None
        end_time = None
        job_count = 0
        
        if opt_req and opt_req.result and 'routes' in opt_req.result:
            # Find this route's data in the optimization result
            # Match by driver_id (team_member_id in result)
            for route_result in opt_req.result['routes']:
                if route_result.get('team_member_id') == route.driver_id:
                    stops = route_result.get('stops', [])
                    if stops:
                        # First stop (depot start) arrival is the start time
                        first_stop = stops[0]
                        if first_stop.get('arrival_time'):
                            start_time = datetime.fromisoformat(first_stop['arrival_time'].replace('Z', '+00:00'))
                        
                        # Last stop (depot end) arrival is the end time
                        last_stop = stops[-1]
                        if last_stop.get('arrival_time'):
                            end_time = datetime.fromisoformat(last_stop['arrival_time'].replace('Z', '+00:00'))
                        
                        # Count job stops
                        job_count = len([s for s in stops if s.get('stop_type') == 'job'])
                    break
        
        # Fallback: try RouteStop table if result JSON didn't provide timing
        if not start_time or not end_time:
            if route.stops:
                sorted_stops = sorted(route.stops, key=lambda s: s.sequence_order or 0)
                
                # Find first stop with any time
                for stop in sorted_stops:
                    if stop.planned_arrival_time:
                        start_time = stop.planned_arrival_time
                        break
                
                # Find last stop with any time
                for stop in reversed(sorted_stops):
                    if stop.planned_departure_time:
                        end_time = stop.planned_departure_time
                        break
                    elif stop.planned_arrival_time:
                        end_time = stop.planned_arrival_time
                        break
                
                if not job_count:
                    job_count = len([s for s in route.stops if s.stop_type == "job"])
        
        if not start_time or not end_time:
            return None
        
        return ScheduleBlock(
            id=f"route_{route.id}",
            type=ScheduleBlockType.route,
            start_time=start_time,
            end_time=end_time,
            title=route_name,
            status=route.status.value if route.status else "scheduled",
            metadata=ScheduleBlockMetadata(
                route_id=route.id,
                stops_count=job_count,
                total_distance_meters=route.total_distance_meters,
                total_duration_seconds=route.total_duration_seconds
            )
        )
    
    def _create_optimized_break_block(
        self,
        route: Route
    ) -> Optional[ScheduleBlock]:
        """
        Create a break block from optimization result's break_info.
        This provides accurate break timing determined by OR-Tools.
        """
        opt_req = route.optimization_request
        if not opt_req or not opt_req.result:
            return None
        
        # Find this route's data in the optimization result
        for route_result in opt_req.result.get('routes', []):
            if route_result.get('team_member_id') == route.driver_id:
                break_info = route_result.get('break_info')
                if not break_info:
                    break
                
                # Safe access with validation
                start_time_str = break_info.get('start_time')
                end_time_str = break_info.get('end_time')
                
                if not start_time_str or not end_time_str:
                    break
                
                try:
                    start_time = datetime.fromisoformat(
                        start_time_str.replace('Z', '+00:00')
                    )
                    end_time = datetime.fromisoformat(
                        end_time_str.replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    break
                
                location = break_info.get('location', {})
                
                return ScheduleBlock(
                    id=f"break_{route.driver_id}_{route.id}",
                    type=ScheduleBlockType.break_time,
                    start_time=start_time,
                    end_time=end_time,
                    title="Break",
                    status=None,
                    metadata=ScheduleBlockMetadata(
                        driver_id=route.driver_id,
                        break_duration_minutes=break_info.get('duration_minutes'),
                        break_location_address=location.get('address_formatted')
                    )
                )
        
        return None
    
    def _create_idle_blocks(
        self,
        route: Route
    ) -> List[ScheduleBlock]:
        """
        Create idle time blocks from optimization result.
        """
        blocks = []
        opt_req = route.optimization_request
        if not opt_req or not opt_req.result:
            return blocks
        
        # Find this route's data in the optimization result
        for route_result in opt_req.result.get('routes', []):
            if route_result.get('team_member_id') == route.driver_id:
                idle_blocks_data = route_result.get('idle_blocks', [])
                
                for i, idle in enumerate(idle_blocks_data):
                    # Safe access with validation
                    start_time_str = idle.get('start_time')
                    end_time_str = idle.get('end_time')
                    
                    if not start_time_str or not end_time_str:
                        continue
                    
                    try:
                        start_time = datetime.fromisoformat(
                            start_time_str.replace('Z', '+00:00')
                        )
                        end_time = datetime.fromisoformat(
                            end_time_str.replace('Z', '+00:00')
                        )
                    except (ValueError, AttributeError):
                        continue
                    
                    location = idle.get('location', {})
                    
                    blocks.append(ScheduleBlock(
                        id=f"idle_{route.id}_{i}",
                        type=ScheduleBlockType.idle,
                        start_time=start_time,
                        end_time=end_time,
                        title="Idle",
                        status=None,
                        metadata=ScheduleBlockMetadata(
                            idle_duration_minutes=idle.get('duration_minutes'),
                            address=location.get('address_formatted')
                        )
                    ))
                break
        
        return blocks
    
    def _create_static_break_block(
        self,
        driver: TeamMember,
        schedule_date: date
    ) -> Optional[ScheduleBlock]:
        """
        Create a break block from driver's static break times.
        Converts break times to datetime for the given date.
        """
        if not driver.break_time_start or not driver.break_time_end:
            return None
        
        # Convert time to datetime for the schedule date
        # Use UTC timezone to match optimization result timestamps
        from datetime import timezone
        start_datetime = datetime.combine(schedule_date, driver.break_time_start, tzinfo=timezone.utc)
        end_datetime = datetime.combine(schedule_date, driver.break_time_end, tzinfo=timezone.utc)
        
        # Handle overnight breaks (end time is next day)
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)
        
        return ScheduleBlock(
            id=f"break_{driver.id}",
            type=ScheduleBlockType.break_time,
            start_time=start_datetime,
            end_time=end_datetime,
            title="Break",
            status=None,
            metadata=ScheduleBlockMetadata(
                driver_id=driver.id
            )
        )


# Singleton instance
schedule_service = ScheduleService()
