from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobUpdate


class CRUDJob(CRUDBase[Job, JobCreate, JobUpdate]):
    """
    CRUD operations for Job model.
    
    Inherits all standard CRUD operations from CRUDBase.
    """
    
    def create(
        self,
        db: Session,
        *,
        obj_in: JobCreate,
        tenant_id: int
    ) -> Job:
        """
        Create a new job with location conversion.
        """
        obj_data = obj_in.model_dump()
        
        # Convert location dict to WKT string if present
        if obj_data.get("location"):
            loc = obj_data["location"]
            # GeoAlchemy2 expects WKT format: POINT(x y) -> POINT(lng lat)
            obj_data["location"] = f"POINT({loc['lng']} {loc['lat']})"
            
        db_obj = self.model(tenant_id=tenant_id, **obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Job,
        obj_in: JobUpdate | Dict[str, Any]
    ) -> Job:
        """
        Update a job with location conversion.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        # Convert location dict to WKT string if present
        if update_data.get("location"):
            loc = update_data["location"]
            # GeoAlchemy2 expects WKT format: POINT(x y) -> POINT(lng lat)
            update_data["location"] = f"POINT({loc['lng']} {loc['lat']})"
            
        return super().update(db=db, db_obj=db_obj, obj_in=update_data)

    def bulk_create(
        self,
        db: Session,
        *,
        jobs_in: list[JobCreate],
        tenant_id: int
    ) -> tuple[list[Job], list[dict]]:
        """
        Bulk create jobs with validation and error handling.
        
        Returns:
            Tuple of (created_jobs, errors)
            - created_jobs: List of successfully created Job instances
            - errors: List of error dicts with row index and error message
        """
        created_jobs = []
        errors = []
        
        for idx, job_data in enumerate(jobs_in):
            try:
                obj_data = job_data.model_dump()
                
                # Convert location dict to WKT string if present
                if obj_data.get("location"):
                    loc = obj_data["location"]
                    obj_data["location"] = f"POINT({loc['lng']} {loc['lat']})"
                
                db_obj = self.model(tenant_id=tenant_id, **obj_data)
                db.add(db_obj)
                db.flush()  # Flush to get ID but don't commit yet
                created_jobs.append(db_obj)
            except Exception as e:
                errors.append({
                    "row": idx,
                    "error": str(e)
                })
        
        # Commit all successful inserts
        if created_jobs:
            db.commit()
            for job in created_jobs:
                db.refresh(job)
        
        return created_jobs, errors

    def update_status(
        self,
        db: Session,
        job_id: int,
        status: JobStatus,
        tenant_id: int
    ) -> Optional[Job]:
        """
        Update job status.
        """
        job = self.get(db=db, id=job_id, tenant_id=tenant_id)
        if job:
            job.status = status
            db.add(job)
            db.commit()
            db.refresh(job)
        return job


# Create a singleton instance
job = CRUDJob(Job)
