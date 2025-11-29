from typing import Optional
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
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
    
    Manages optimization job lifecycle using ProcessPoolExecutor.
    Designed for easy migration to Celery in the future.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize optimization service with ProcessPoolExecutor.
        
        Args:
            max_workers: Maximum number of worker processes (default: 4)
        """
        self.crud = optimization_crud
        # Get max workers from environment or use default
        max_workers = int(os.getenv("OPTIMIZATION_MAX_WORKERS", max_workers))
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        logger.info(f"OptimizationService initialized with {max_workers} workers")
    
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
        
        # Submit to ProcessPoolExecutor
        # Note: We pass the request_id and database URL, not the session
        # The worker will create its own session
        from app.database import DATABASE_URL
        future = self.executor.submit(
            run_optimization_worker,
            request_id=opt_request.id,
            tenant_id=tenant_id,
            database_url=DATABASE_URL
        )
        
        logger.info(f"Optimization request {opt_request.id} submitted to worker pool")
        
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
    
    def __del__(self):
        """Cleanup executor on service destruction."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


def run_optimization_worker(request_id: int, tenant_id: int, database_url: str):
    """
    Worker function to run optimization logic.
    
    This function runs in a separate process. It:
    1. Creates its own database session
    2. Updates status to processing
    3. Runs optimization logic (placeholder for now)
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
    # This prevents circular import issues in the worker process
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.depot import Depot
    from app.models.vehicle import Vehicle
    from app.models.team_member import TeamMember
    from app.models.job import Job
    from app.models.route import Route, RouteStop
    from app.models.optimization_request import OptimizationRequest, OptimizationStatus
    
    # NOW we can safely import CRUD after models are initialized
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
        
        # ============================================================
        # PLACEHOLDER: Optimization logic goes here
        # ============================================================
        # In the future, this will call GraphHopper, Google OR-Tools, etc.
        # For now, we'll simulate processing with a delay
        logger.info(
            f"Running optimization for request {request_id}: "
            f"depot={opt_request.depot_id}, jobs={opt_request.job_ids}, "
            f"team_members={opt_request.team_member_ids}, goal={opt_request.optimization_goal}"
        )
        
        # Simulate optimization work
        time.sleep(5)  # Simulate processing time
        
        # Create a placeholder result
        result_data = {
            "status": "success",
            "routes": [
                {
                    "team_member_id": opt_request.team_member_ids[0] if opt_request.team_member_ids else None,
                    "job_ids": opt_request.job_ids[:3] if len(opt_request.job_ids) >= 3 else opt_request.job_ids,
                    "total_distance_km": 25.5,
                    "total_time_minutes": 120
                }
            ],
            "optimization_goal": opt_request.optimization_goal.value,
            "total_jobs": len(opt_request.job_ids),
            "total_team_members": len(opt_request.team_member_ids),
            "message": "This is a placeholder result. Real optimization logic will be implemented later."
        }
        # ============================================================
        
        # Store the result using CRUD layer
        optimization_request.store_result(
            db=db,
            request_id=request_id,
            tenant_id=tenant_id,
            result=result_data
        )
        
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
