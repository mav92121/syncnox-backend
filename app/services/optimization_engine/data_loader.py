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
from datetime import datetime, time, timedelta
from app.crud.depot import depot as depot_crud
from app.crud.job import job as job_crud
from app.crud.team_member import team_member as team_member_crud
from app.crud.vehicle import vehicle as vehicle_crud


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
        
        # Build location index: 0 = depot, 1..N = jobs
        self.location_index = {0: depot}
        for idx, job in enumerate(jobs, start=1):
            self.location_index[idx] = job
        
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
        tenant_id: int
    ) -> OptimizationData:
        """
        Load all required data for optimization.
        
        Args:
            depot_id: Depot ID
            job_ids: List of job IDs to optimize
            team_member_ids: List of team member IDs available
            scheduled_date: Date for optimization
            tenant_id: Tenant ID for isolation
            
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
