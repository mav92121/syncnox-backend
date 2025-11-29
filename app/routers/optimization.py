from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.optimization import OptimizationRequestCreate, OptimizationRequestResponse
from app.services.optimization import optimization_service
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger

router = APIRouter()


@router.post("/requests", response_model=OptimizationRequestResponse, status_code=status.HTTP_201_CREATED)
def create_optimization_request(
    request_data: OptimizationRequestCreate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Create a new optimization request.
    
    The request is immediately queued and submitted to a worker process.
    The client should poll GET /optimization/requests/{id} to check status.
    
    Args:
        request_data: Optimization request parameters
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Created optimization request with status=queued
    
    Example:
        ```json
        {
            "depot_id": 1,
            "job_ids": [1, 2, 3, 4, 5],
            "team_member_ids": [1, 2],
            "scheduled_date": "2025-12-01",
            "optimization_goal": "minimum_time"
        }
        ```
    """
    try:
        logger.info(
            f"Creating optimization request: tenant_id={_tenant_id}, "
            f"depot_id={request_data.depot_id}"
        )
        result = optimization_service.create_optimization_request(
            db=db,
            request_data=request_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Optimization request created: id={result.id}, status={result.status}")
        return result
    except Exception as e:
        logger.error(f"Error creating optimization request: {type(e).__name__}: {str(e)}")
        raise


@router.get("/requests/{request_id}", response_model=OptimizationRequestResponse)
def get_optimization_request(
    request_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Get the status and results of an optimization request.
    
    Use this endpoint to poll the status of a previously created optimization request.
    
    Status progression:
    - queued: Request is waiting to be processed
    - processing: Worker is currently running optimization
    - completed: Optimization finished successfully (check 'result' field)
    - failed: Optimization failed (check 'error_message' field)
    
    Args:
        request_id: Optimization request ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Optimization request with current status and results (if completed)
        
    Raises:
        HTTPException 404: If request not found
    """
    return optimization_service.get_optimization_request(
        db=db,
        request_id=request_id,
        tenant_id=_tenant_id
    )
