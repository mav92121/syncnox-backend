from datetime import datetime
from typing import List
import redis
from rq import Queue
from app.core.config import settings
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud import optimization_request as optimization_crud
from app.schemas.optimization import OptimizationRequestCreate, OptimizationRequestResponse
from app.models.optimization_request import OptimizationRequest, OptimizationStatus
from app.core.logging_config import logger
import os


class OptimizationService:
    """
    Service layer for optimization request business logic.
    
    Manages optimization job lifecycle using Redis Queue (RQ).
    Designed for easy migration to Celery in the future.
    """
    
    def __init__(self):
        """
        Initialize optimization service with Redis Queue.
        """
        self.crud = optimization_crud
        
        # Initialize Redis connection and Queue safely
        try:
            self.redis_conn = redis.from_url(settings.REDIS_URL)
            self.queue = Queue(settings.OPTIMIZATION_QUEUE_NAME, connection=self.redis_conn)
            logger.info(f"OptimizationService initialized with queue '{settings.OPTIMIZATION_QUEUE_NAME}'")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_conn = None
            self.queue = None
    
    def create_optimization_request(
        self,
        db: Session,
        request_data: OptimizationRequestCreate,
        tenant_id: int
    ) -> OptimizationRequest:
        """
        Create a new optimization request and submit to worker pool.
        
        Args:
            db: Database session
            request_data: Optimization request creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created OptimizationRequest with status=queued
        """
        logger.info(
            f"Creating optimization request: tenant_id={tenant_id}, "
            f"depot_id={request_data.depot_id}, jobs={len(request_data.job_ids)}, "
            f"team_members={len(request_data.team_member_ids)}"
        )
        
        # Create the request in database with status=queued
        opt_request = self.crud.create(
            db=db,
            obj_in=request_data,
            tenant_id=tenant_id
        )
        
        logger.info(f"Optimization request created: id={opt_request.id}, status={opt_request.status}")
        
        # Submit to RQ
        # Note: We pass the request_id and database URL, not the session
        # The worker will create its own session
        from app.database import DATABASE_URL
        
        if not self.queue:
            # Try to reconnect if queue is missing
            try:
                self.redis_conn = redis.from_url(settings.REDIS_URL)
                self.queue = Queue(settings.OPTIMIZATION_QUEUE_NAME, connection=self.redis_conn)
            except Exception as e:
                logger.error(f"Still cannot connect to Redis: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Optimization service is currently unavailable (Redis down)"
                )

        job = self.queue.enqueue(
            run_optimization_worker,
            request_id=opt_request.id,
            tenant_id=tenant_id,
            database_url=DATABASE_URL,
            job_timeout='5m'  # 5 minute timeout
        )
        
        logger.info(f"Optimization request {opt_request.id} submitted to queue, job_id={job.id}")
        
        return opt_request
    
    def get_optimization_request(
        self,
        db: Session,
        request_id: int,
        tenant_id: int
    ) -> OptimizationRequest:
        """
        Get an optimization request by ID with tenant isolation.
        
        Args:
            db: Database session
            request_id: Optimization request ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            OptimizationRequest instance
            
        Raises:
            HTTPException 404: If request not found
        """
        opt_request = self.crud.get(db=db, id=request_id, tenant_id=tenant_id)
        
        if not opt_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimization request not found"
            )
        
        return opt_request
    

    
    def get_optimization_requests(
        self,
        db: Session,
        tenant_id: int
    ) -> List[OptimizationRequest]:
        """
        Get all optimization requests for the current tenant.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            
        Returns:
            List of optimization requests with current status and results (if completed)
        """
        return self.crud.get_multi(db=db, tenant_id=tenant_id)


def run_optimization_worker(request_id: int, tenant_id: int, database_url: str):
    """
    Worker function to run optimization logic.
    
    This function runs in a separate process. It:
    1. Creates its own database session
    2. Updates status to processing
    3. Runs optimization logic
    4. Stores results
    5. Updates status to completed/failed
    
    Args:
        request_id: Optimization request ID
        tenant_id: Tenant ID for isolation
        database_url: Database connection URL
        
    Note:
        This function is designed to be easily converted to a Celery task.
        Just add @celery.task decorator and it will work with minimal changes.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import time
    import traceback
    
    # IMPORTANT: Import all models first to ensure proper initialization order
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.depot import Depot
    from app.models.vehicle import Vehicle
    from app.models.team_member import TeamMember
    from app.models.job import Job
    from app.models.route import Route, RouteStop
    from app.models.optimization_request import OptimizationRequest, OptimizationStatus
    
    from app.crud.optimization_request import optimization_request
    
    # Create a new database session for this worker
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        logger.info(f"Worker started for optimization request {request_id}")
        
        # Use CRUD layer to update status to processing
        optimization_request.update_status(
            db=db,
            request_id=request_id,
            tenant_id=tenant_id,
            status=OptimizationStatus.PROCESSING,
            started_at=datetime.utcnow()
        )
        logger.info(f"Optimization request {request_id} status updated to PROCESSING")
        
        # Get the request details using CRUD layer
        opt_request = optimization_request.get(db=db, id=request_id, tenant_id=tenant_id)
        if not opt_request:
            raise Exception(f"Optimization request {request_id} not found")
        
        logger.info(
            f"Running optimization for request {request_id}: "
            f"depot={opt_request.depot_id}, jobs={opt_request.job_ids}, "
            f"team_members={opt_request.team_member_ids}, goal={opt_request.optimization_goal}"
        )
        
        # ============================================================
        # OPTIMIZATION LOGIC
        # ============================================================
        
        # Import optimization modules
        from app.services.optimization_engine.data_loader import OptimizationDataLoader
        from app.services.optimization_engine.graphhopper_client import GraphHopperClient
        from app.services.optimization_engine.solver import VRPSolver
        from app.services.optimization_engine.result_formatter import ResultFormatter
        from app.services.optimization_engine.route_storage import RouteStorage
        
        # Step 1: Load and validate data
        logger.info("Step 1: Loading optimization data")
        data_loader = OptimizationDataLoader(db)
        data = data_loader.load(
            depot_id=opt_request.depot_id,
            job_ids=opt_request.job_ids,
            team_member_ids=opt_request.team_member_ids,
            scheduled_date=opt_request.scheduled_date,
            tenant_id=tenant_id
        )
        
        # Step 2: Get distance/duration matrix from GraphHopper
        logger.info("Step 2: Computing distance/duration matrix")
        gh_client = GraphHopperClient()
        
        # Get depot coordinates
        depot_coords = gh_client.geometry_to_coords(data.depot.location)
        
        # Get job coordinates
        job_coords = [gh_client.geometry_to_coords(job.location) for job in data.jobs]
        
        # Determine vehicle type (use first team member's vehicle or default to car)
        vehicle_type = "car"
        if data.team_members and data.team_members[0].vehicle_id:
            vehicle = data.vehicles.get(data.team_members[0].vehicle_id)
            if vehicle and vehicle.type:
                vehicle_type = vehicle.type.value
        
        # Get matrix
        matrix = gh_client.get_matrix_for_optimization(
            depot_location=depot_coords,
            job_locations=job_coords,
            vehicle_type=vehicle_type
        )
        
        distance_matrix = matrix["distances"]
        duration_matrix = matrix["durations"]
        
        # Step 3: Solve VRP
        logger.info("Step 3: Solving VRP with OR-Tools")
        solver = VRPSolver(
            data=data,
            distance_matrix=distance_matrix,
            duration_matrix=duration_matrix,
            optimization_goal=opt_request.optimization_goal
        )
        
        solution = solver.solve(time_limit_seconds=30)
        
        if not solution:
            raise Exception("No feasible solution found")
        
        # Step 4: Format results
        logger.info("Step 4: Formatting results")
        formatter = ResultFormatter(data)
        result_data = formatter.format(solution)
        
        # Step 5: Store results in OptimizationRequest
        logger.info("Step 5: Storing results")
        optimization_request.store_result(
            db=db,
            request_id=request_id,
            tenant_id=tenant_id,
            result=result_data
        )
        
        # Step 6: Store routes in Route/RouteStop tables
        logger.info("Step 6: Storing routes in Route/RouteStop tables")
        route_storage = RouteStorage(db, data)
        route_ids = route_storage.store_routes(
            optimization_request_id=request_id,
            formatted_result=result_data,
            tenant_id=tenant_id
        )
        
        logger.info(f"Created {len(route_ids)} routes: {route_ids}")
        
        # ============================================================
        
        # Update status to completed using CRUD layer
        optimization_request.update_status(
            db=db,
            request_id=request_id,
            tenant_id=tenant_id,
            status=OptimizationStatus.COMPLETED,
            completed_at=datetime.utcnow()
        )
        
        logger.info(f"Optimization request {request_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Optimization request {request_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update status to failed with error message using CRUD layer
        try:
            optimization_request.update_status(
                db=db,
                request_id=request_id,
                tenant_id=tenant_id,
                status=OptimizationStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
        except Exception as update_error:
            logger.error(f"Failed to update error status: {str(update_error)}")
    
    finally:
        db.close()
        engine.dispose()


# Create singleton instance
optimization_service = OptimizationService()
