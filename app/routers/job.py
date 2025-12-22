from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.job import JobCreate, JobUpdate, JobResponse
from app.services.job import job_service
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger
from datetime import date as date_type

router = APIRouter()

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Create a new job.
    
    The tenant is automatically identified from the JWT token.
    
    Args:
        job_data: Job creation data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Created job
    """
    try:
        logger.info(f"Creating job: tenant_id={_tenant_id}")
        result = job_service.create_job(
            db=db,
            job_data=job_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Job created successfully: id={result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating job: {type(e).__name__}: {str(e)}")
        raise

@router.get("", response_model=List[JobResponse])
def get_jobs(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    date: date_type | None = None,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve all jobs for your tenant.
    
    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        status: Optional status to filter by
        date: Optional date to filter by (scheduled_date)
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        List of jobs belonging to your tenant
    """
    return job_service.get_jobs(
        db=db,
        tenant_id=_tenant_id,
        skip=skip,
        limit=limit,
        status=status,
        date=date
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Retrieve a specific job by ID.
    
    Args:
        job_id: Job ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Job details
        
    Raises:
        HTTPException 404: If job not found
    """
    return job_service.get_job(
        db=db,
        job_id=job_id,
        tenant_id=_tenant_id
    )


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Update an existing job.
    
    Args:
        job_id: Job ID
        job_data: Job update data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Updated job
        
    Raises:
        HTTPException 404: If job not found
    """
    return job_service.update_job(
        db=db,
        job_id=job_id,
        job_data=job_data,
        tenant_id=_tenant_id
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Delete a job.
    
    Args:
        job_id: Job ID
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Raises:
        HTTPException 404: If job not found
    """
    job_service.delete_job(
        db=db,
        job_id=job_id,
        tenant_id=_tenant_id
    )
    return None


@router.post("/bulk/delete", status_code=status.HTTP_200_OK)
def bulk_delete_jobs(
    job_ids: List[int],
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Bulk delete jobs.
    
    Args:
        job_ids: List of job IDs to delete
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Summary of deleted jobs
    """
    try:
        result = job_service.bulk_delete_jobs(
            db=db,
            job_ids=job_ids,
            tenant_id=_tenant_id
        )
        logger.info(f"Bulk delete completed: deleted={result['deleted']}")
        return result
    except Exception as e:
        logger.error(f"Error in bulk delete: {type(e).__name__}: {str(e)}")
        raise


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_jobs(
    jobs_data: List[JobCreate],
    db: Session = Depends(get_db),
    _tenant_id: int = Depends(get_tenant_id)
):
    """
    Bulk create multiple jobs.
    
    The tenant is automatically identified from the JWT token.
    
    Args:
        jobs_data: List of job creation data
        db: Database session
        _tenant_id: Tenant context (auto-set from JWT)
    
    Returns:
        Summary of created jobs and any errors
    """
    try:
        logger.info(f"Bulk creating {len(jobs_data)} jobs: tenant_id={_tenant_id}")
        result = job_service.bulk_create_jobs(
            db=db,
            jobs_data=jobs_data,
            tenant_id=_tenant_id
        )
        logger.info(f"Bulk create completed: created={result['created']}, failed={result['failed']}")
        return result
    except Exception as e:
        logger.error(f"Error in bulk create: {type(e).__name__}: {str(e)}")
        raise
