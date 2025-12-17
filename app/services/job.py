from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud import job as job_crud
from app.schemas.job import JobCreate, JobUpdate
from app.models.job import Job
from datetime import date as date_type


class JobService:
    """
    Service layer for job business logic.
    
    This layer handles business rules, validation, and coordination
    of CRUD operations.
    """
    
    def __init__(self):
        self.crud = job_crud
    
    def get_job(
        self,
        db: Session,
        job_id: int,
        tenant_id: int
    ) -> Job:
        """
        Get a job by ID with tenant isolation.
        
        Args:
            db: Database session
            job_id: Job ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            Job instance
            
        Raises:
            HTTPException 404: If job not found
        """
        job = self.crud.get(db=db, id=job_id, tenant_id=tenant_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return job

    def get_jobs(
        self,
        db: Session,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        date: date_type | None = None
    ) -> List[Job]:
        """
        Get all jobs with tenant isolation.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status to filter by
            date: Optional date to filter by (scheduled_date)
            
        Returns:
            List of Job instances
        """
        return self.crud.get_multi(
            db=db, 
            skip=skip, 
            limit=limit, 
            tenant_id=tenant_id,
            status=status,
            date=date
        )
    
    def create_job(
        self,
        db: Session,
        job_data: JobCreate,
        tenant_id: int
    ) -> Job:
        """
        Create a new job.
        
        Args:
            db: Database session
            job_data: Job creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created Job instance
        """
        return self.crud.create(db=db, obj_in=job_data, tenant_id=tenant_id)
    
    def update_job(
        self,
        db: Session,
        job_id: int,
        job_data: JobUpdate,
        tenant_id: int
    ) -> Job:
        """
        Update a job.
        
        Args:
            db: Database session
            job_id: Job ID
            job_data: Job update data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Updated Job instance
            
        Raises:
            HTTPException 404: If job not found
        """
        # Get existing job
        job = self.get_job(db=db, job_id=job_id, tenant_id=tenant_id)
        
        # Update the job
        return self.crud.update(db=db, db_obj=job, obj_in=job_data)
    
    def delete_job(
        self,
        db: Session,
        job_id: int,
        tenant_id: int
    ) -> None:
        """
        Delete a job.
        
        Args:
            db: Database session
            job_id: Job ID
            tenant_id: Tenant ID for isolation
            
        Raises:
            HTTPException 404: If job not found
        """
        deleted = self.crud.delete(db=db, id=job_id, tenant_id=tenant_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

    def bulk_create_jobs(
        self,
        db: Session,
        jobs_data: List[JobCreate],
        tenant_id: int
    ) -> dict:
        """
        Bulk create jobs.
        
        Args:
            db: Database session
            jobs_data: List of job creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Dict with created count, failed count, and error details
        """
        created_jobs, errors = self.crud.bulk_create(
            db=db,
            jobs_in=jobs_data,
            tenant_id=tenant_id
        )
        
        return {
            "created": len(created_jobs),
            "failed": len(errors),
            "errors": errors,
            "job_ids": [job.id for job in created_jobs]
        }


# Create a singleton instance
job_service = JobService()
