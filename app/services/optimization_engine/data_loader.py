"""
Data loader for optimization requests.

Loads and validates all required data from the database for route optimization.
"""

from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.models.depot import Depot
from app.models.job import Job, JobStatus
from app.models.team_member import TeamMember
from app.models.vehicle import Vehicle
from datetime import date as date_type, datetime, time, timedelta
from app.crud.depot import depot as depot_crud
from app.crud.job import job as job_crud
from app.crud.team_member import team_member as team_member_crud
from app.crud.vehicle import vehicle as vehicle_crud
from app.crud.route import route as route_crud
from app.models.team_member import TeamMemberStatus


class _DynamicLocation:
    """
    Lightweight location wrapper for dynamic vehicle start positions.
    These represent the last job location of a driver's prior route.
    Not a DB model — used only within the solver session.
    """
    __slots__ = ('location',)
    
    def __init__(self, location: Any):
        self.location = location


class OptimizationData:
    """Container for optimization data."""
    
    def __init__(
        self,
        depot: Depot,
        jobs: List[Job],
        team_members: List[TeamMember],
        vehicles: Dict[int, Vehicle],
        scheduled_date: datetime
    ):
        self.depot = depot
        self.jobs = jobs
        self.team_members = team_members
        self.vehicles = vehicles  # vehicle_id -> Vehicle
        self.scheduled_date = scheduled_date
        
        # Build location index: 0 = depot, 1..N = jobs, (N+1..) = dynamic vehicle starts
        self.location_index = {0: depot}
        for idx, job in enumerate(jobs, start=1):
            self.location_index[idx] = job
            
        # Add dynamic start locations for team members who continue from a prior route.
        # _prior_route_end_location is set on the TM instance (not persisted) by
        # _check_driver_availability before OptimizationData is constructed.
        self.team_member_starts: Dict[int, int] = {}  # tm.id -> location index
        current_idx: int = len(jobs) + 1
        
        for tm in team_members:
            prior_loc = getattr(tm, '_prior_route_end_location', None)
            if prior_loc is not None:
                self.location_index[current_idx] = _DynamicLocation(prior_loc)
                self.team_member_starts[tm.id] = current_idx
                current_idx += 1
            else:
                self.team_member_starts[tm.id] = 0  # Default to depot
        
        # Build reverse index: job_id -> location_index
        self.job_id_to_index = {job.id: idx for idx, job in enumerate(jobs, start=1)}
        
        # Build team member index
        self.team_member_index = {tm.id: idx for idx, tm in enumerate(team_members)}
    
    def get_location_coords(self, location_idx: int) -> Tuple[float, float]:
        """Get (lon, lat) coordinates for a location index."""
        from app.services.optimization_engine.routing_client import get_routing_client
        
        location = self.location_index[location_idx]
        client = get_routing_client()  # Just for geometry conversion
        return client.geometry_to_coords(location.location)
    
    def get_all_location_coords(self) -> List[Tuple[float, float]]:
        """Get coordinates for all locations (depot + jobs) in order."""
        coords = []
        for idx in sorted(self.location_index.keys()):
            coords.append(self.get_location_coords(idx))
        return coords


class OptimizationDataLoader:
    """Loads and validates data for optimization."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def load(
        self,
        depot_id: int,
        job_ids: List[int],
        team_member_ids: List[int],
        scheduled_date: datetime,
        tenant_id: int,
        exclude_route_ids: Optional[List[int]] = None,
        custom_starts: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> OptimizationData:
        """
        Load all required data for optimization.
        
        Args:
            depot_id: Depot ID
            job_ids: List of job IDs to optimize
            team_member_ids: List of team member IDs available
            scheduled_date: Date for optimization
            tenant_id: Tenant ID for isolation
            exclude_route_ids: List of route IDs to ignore when checking availability
            custom_starts: Dict mapping team_member_id to custom start state (location, ready_time, break_taken)
            
        Returns:
            OptimizationData instance
            
        Raises:
            ValueError: If any required data is missing or invalid
        """
        logger.info(
            f"Loading optimization data: depot={depot_id}, "
            f"jobs={len(job_ids)}, team_members={len(team_member_ids)}"
        )
        
        # Load depot using CRUD
        depot = self._load_depot(depot_id, tenant_id)
        
        # Load jobs using CRUD
        jobs = self._load_jobs(job_ids, tenant_id)
        
        # Load team members using CRUD
        team_members = self._load_team_members(team_member_ids, tenant_id)
        
        # Load vehicles for team members using CRUD
        vehicles = self._load_vehicles(team_members, tenant_id)
        
        # Check and adjust driver availability
        team_members = self._check_driver_availability(
            team_members, scheduled_date, tenant_id, exclude_route_ids, custom_starts
        )
        
        # Validate data
        self._validate_data(depot, jobs, team_members)
        
        logger.info("Optimization data loaded and validated successfully")
        
        return OptimizationData(
            depot=depot,
            jobs=jobs,
            team_members=team_members,
            vehicles=vehicles,
            scheduled_date=scheduled_date
        )
    
    def _load_depot(self, depot_id: int, tenant_id: int) -> Depot:
        """Load depot by ID using CRUD."""
        depot = depot_crud.get(db=self.db, id=depot_id, tenant_id=tenant_id)
        
        if not depot:
            raise ValueError(f"Depot {depot_id} not found")
        
        if not depot.location:
            raise ValueError(f"Depot {depot_id} has no location")
        
        logger.debug(f"Loaded depot: {depot.name}")
        return depot
    
    def _load_jobs(self, job_ids: List[int], tenant_id: int) -> List[Job]:
        """Load jobs by IDs using CRUD."""
        jobs = job_crud.get_multi_by_ids(
            db=self.db,
            job_ids=job_ids,
            tenant_id=tenant_id,
            status=JobStatus.draft
        )
        
        if len(jobs) != len(job_ids):
            found_ids = {j.id for j in jobs}
            missing_ids = set(job_ids) - found_ids
            raise ValueError(f"Jobs not found or not in draft status: {missing_ids}")
        
        # Validate all jobs have locations
        for job in jobs:
            if not job.location:
                raise ValueError(f"Job {job.id} has no location")
        
        logger.debug(f"Loaded {len(jobs)} jobs")
        return jobs
    
    def _load_team_members(
        self,
        team_member_ids: List[int],
        tenant_id: int
    ) -> List[TeamMember]:
        """Load team members by IDs using CRUD."""
        team_members = team_member_crud.get_multi_by_ids(
            db=self.db,
            ids=team_member_ids,
            tenant_id=tenant_id
        )
        
        if len(team_members) != len(team_member_ids):
            found_ids = {tm.id for tm in team_members}
            missing_ids = set(team_member_ids) - found_ids
            raise ValueError(f"Team members not found: {missing_ids}")
        
        logger.debug(f"Loaded {len(team_members)} team members")
        return team_members
    
    def _load_vehicles(
        self,
        team_members: List[TeamMember],
        tenant_id: int
    ) -> Dict[int, Vehicle]:
        """Load vehicles for team members using CRUD."""
        vehicle_ids = [tm.vehicle_id for tm in team_members if tm.vehicle_id]
        
        if not vehicle_ids:
            logger.warning("No vehicles assigned to team members")
            return {}
        
        vehicles = vehicle_crud.get_multi_by_ids(
            db=self.db,
            ids=vehicle_ids,
            tenant_id=tenant_id
        )
        
        # Create mapping
        vehicle_map = {v.id: v for v in vehicles}
        
        logger.debug(f"Loaded {len(vehicles)} vehicles")
        return vehicle_map
    
    def _validate_data(
        self,
        depot: Depot,
        jobs: List[Job],
        team_members: List[TeamMember]
    ) -> None:
        """Validate loaded data."""
        if not jobs:
            raise ValueError("No jobs to optimize")
        
        if not team_members:
            raise ValueError("No team members available")
        
        # Check if we have more jobs than can be handled
        # This is a soft check - OR-Tools will handle infeasibility
        logger.info(
            f"Validation: {len(jobs)} jobs, {len(team_members)} team members"
        )

    def _check_driver_availability(
        self,
        team_members: List[TeamMember],
        scheduled_date: datetime,
        tenant_id: int,
        exclude_route_ids: Optional[List[int]] = None,
        custom_starts: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> List[TeamMember]:
        """
        Check driver availability and adjust time windows based on existing routes.
        
        Args:
            team_members: List of TeamMember to check
            scheduled_date: Target optimization date
            tenant_id: Tenant ID for isolation
            exclude_route_ids: List of route IDs to ignore
            custom_starts: Dict mapping team_member_id to custom start state
            
        Returns:
            List of valid TeamMember objects with potentially adjusted working hours.
            
        Raises:
            ValueError: If an invalid/unavailable driver is provided.
        """
        # 1. Status Check
        for tm in team_members:
            if tm.status != TeamMemberStatus.active:
                raise ValueError(
                    f"Team member '{tm.name}' is unavailable (status: {tm.status.value})"
                )
        
        # 2. Schedule Check & Time Window Adjustment
        driver_ids = [tm.id for tm in team_members]
        if isinstance(scheduled_date, datetime):
            date_to_check = scheduled_date.date()
        else:
            date_to_check = scheduled_date
            
        existing_routes = route_crud.get_active_routes_by_drivers_and_date(
            db=self.db,
            driver_ids=driver_ids,
            scheduled_date=date_to_check,
            tenant_id=tenant_id
        )
        
        if exclude_route_ids:
            existing_routes = [r for r in existing_routes if r.id not in exclude_route_ids]
        
        if not existing_routes:
            return team_members
            
        # Group existing routes by driver
        routes_by_driver: Dict[int, list] = {}
        for r in existing_routes:
            if r.driver_id:
                routes_by_driver.setdefault(r.driver_id, []).append(r)
        
        valid_team_members = []
        
        for tm in team_members:
            custom_start = custom_starts.get(tm.id) if custom_starts else None
            
            # Set transient state attributes (NOT persisted, used only during optimization session)
            if custom_start:
                tm._prior_route_end_location = custom_start.get("location")
                tm._ready_time = custom_start.get("ready_time", tm.work_start_time)
                tm._break_taken = custom_start.get("break_taken", False)
                valid_team_members.append(tm)
                continue
                
            tm._prior_route_end_location = None  # geometry of last stop's job location
            tm._ready_time: Optional[time] = tm.work_start_time  # effective shift start
            tm._break_taken = False  # whether break was already consumed in prior route
            
            # If no routes, driver is fully available
            if tm.id not in routes_by_driver:
                valid_team_members.append(tm)
                continue
                
            driver_routes = routes_by_driver[tm.id]
            latest_end_time: Optional[time] = None
            latest_stop = None
            
            for r in driver_routes:
                # Find latest stop departure/arrival time using RouteStop
                # Assuming stops are loaded (selectinload used in crud)
                if r.stops:
                    for stop in r.stops:
                        # Prefer departure time, fallback to arrival time
                        stop_time = stop.planned_departure_time or stop.planned_arrival_time
                        if stop_time:
                            # stop_time might be naive datetime or time object
                            t: time
                            if isinstance(stop_time, datetime):
                                t = stop_time.time()
                            else:
                                t = stop_time
                                
                            if latest_end_time is None:
                                latest_end_time = t
                                latest_stop = stop
                            else:
                                if t > latest_end_time:
                                    latest_end_time = t
                                    latest_stop = stop
            
            if latest_end_time:
                # Update effective start time while preserving the original work_start_time
                if not tm.work_start_time or latest_end_time > tm.work_start_time:
                    tm._ready_time = latest_end_time
                    
                # Store the prior route's end location for use as a custom vehicle start node.
                # We use _prior_route_end_location to avoid shadowing the DB-mapped start_location column.
                if latest_stop:
                    job = getattr(latest_stop, 'job', None)
                    if job and getattr(job, 'location', None):
                        tm._prior_route_end_location = job.location
                    
                # Evaluate break state: if the prior route ran past the break window end,
                # we can safely assume the break was already taken.
                if tm.break_time_end:
                    tm_break_end: time
                    raw_end = tm.break_time_end
                    tm_break_end = raw_end.time() if isinstance(raw_end, datetime) else raw_end
                    if latest_end_time > tm_break_end:
                        tm._break_taken = True
                    
                # Check if they are fully booked (effective start >= shift end)
                if tm.work_end_time and tm._ready_time:
                    rt = tm._ready_time
                    ready_t: time = rt.time() if isinstance(rt, datetime) else rt
                    et = tm.work_end_time
                    work_end_t: time = et.time() if isinstance(et, datetime) else et
                    
                    max_end_dt = datetime.combine(date_to_check, work_end_t)
                    if getattr(tm, 'allowed_overtime', False):
                        max_end_dt += timedelta(hours=2)
                        
                    if datetime.combine(date_to_check, ready_t) >= max_end_dt:
                        raise ValueError(
                            f"Team member '{tm.name}' is fully booked on {date_to_check} "
                            f"(existing routes end at {latest_end_time}, "
                            f"shift ends at {max_end_dt.time()})"
                        )
                
                logger.info(
                    f"Driver {tm.id} ({tm.name}): ready={tm._ready_time}, "
                    f"prior_end_loc={'set' if tm._prior_route_end_location else 'depot'}, "
                    f"break_taken={tm._break_taken}"
                )
            
            valid_team_members.append(tm)
            
        return valid_team_members
