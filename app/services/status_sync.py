from sqlalchemy.orm import Session
from sqlalchemy import select, func, cast, String, and_

from app.models.job import Job, JobStatus
from app.models.route import Route, RouteStop, RouteStatus
from app.models.optimization_request import OptimizationRequest
from app.core.logging_config import logger

def sync_route_status_for_job(db: Session, job_id: int) -> None:
    """
    Synchronizes the Route and OptimizationRequest status when a job status changes.
    
    Logic:
    1. Find all Routes that contain this job.
    2. For each Route:
       a. Check the status of all its associated jobs.
       b. If any job is in_transit -> Route is in_transit
       c. If all jobs are completed -> Route is completed
       d. Otherwise -> Route is scheduled
    3. For each unique OptimizationRequest associated with these Routes:
       a. Check the status of all its associated Routes.
       b. If any Route is in_transit -> Request is in_transit
       c. If all Routes are completed -> Request is completed
       d. Otherwise -> Request is scheduled
    """
    nested = db.begin_nested()
    try:
        # Find all routes that contain this job
        stmt = (
            select(Route)
            .join(RouteStop, Route.id == RouteStop.route_id)
            .where(RouteStop.job_id == job_id)
        )
        routes = db.execute(stmt).scalars().all()
        
        if not routes:
            return
            
        opt_request_ids = set()
        
        for route in routes:
            if route.optimization_request_id:
                opt_request_ids.add(route.optimization_request_id)
                
            # Get all jobs for this route
            job_status_counts = (
                select(
                    Job.status,
                    func.count(Job.id).label("count")
                )
                .join(RouteStop, RouteStop.job_id == Job.id)
                .where(
                    RouteStop.route_id == route.id,
                    RouteStop.stop_type == 'job'
                )
                .group_by(Job.status)
            )
            
            results = db.execute(job_status_counts).all()
            
            counts = {str(row.status): row.count for row in results}
            total_jobs = sum(counts.values())
            
            # Note: The database stores enums, which get converted to Enum objects.
            # Using strings for flexibility
            in_transit_count = counts.get(JobStatus.in_transit.value, 0) + counts.get('JobStatus.in_transit', 0)
            completed_count = counts.get(JobStatus.completed.value, 0) + counts.get('JobStatus.completed', 0)
            
            new_status = RouteStatus.scheduled
            
            if in_transit_count > 0:
                new_status = RouteStatus.in_transit
            elif completed_count == total_jobs and total_jobs > 0:
                # Need > 0 check to prevent empty routes from being marked completed
                new_status = RouteStatus.completed
            elif completed_count > 0:
                # If some are completed but not all, and none are in transit, 
                # we consider the route in transit (driver is working on it)
                new_status = RouteStatus.in_transit
                
            if route.status != new_status:
                route.status = new_status
                db.add(route)
                logger.info(f"Route {route.id} status updated to {new_status}")
                
        # To avoid reading stale data (since we haven't committed the routes yet),
        # we flush the session so the new Route statuses are visible to the next query.
        db.flush()
                
        # Now update OptimizationRequests
        for req_id in opt_request_ids:
            req = db.get(OptimizationRequest, req_id)
            if not req:
                continue
                
            # Get statuses of all routes for this request
            route_status_counts = (
                select(
                    Route.status,
                    func.count(Route.id).label("count")
                )
                .where(Route.optimization_request_id == req_id)
                .group_by(Route.status)
            )
            
            results = db.execute(route_status_counts).all()
            counts = {str(row.status): row.count for row in results}
            total_routes = sum(counts.values())
            
            in_transit_count = counts.get(RouteStatus.in_transit.value, 0) + counts.get('RouteStatus.in_transit', 0)
            completed_count = counts.get(RouteStatus.completed.value, 0) + counts.get('RouteStatus.completed', 0)
            
            new_status = RouteStatus.scheduled
            
            if in_transit_count > 0:
                new_status = RouteStatus.in_transit
            elif completed_count == total_routes and total_routes > 0:
                new_status = RouteStatus.completed
            elif completed_count > 0:
                 new_status = RouteStatus.in_transit
                 
            if req.route_status != new_status:
                req.route_status = new_status
                db.add(req)
                logger.info(f"OptimizationRequest {req.id} route_status updated to {new_status}")
                
        nested.commit()
    except Exception as e:
        nested.rollback()
        logger.error(f"Error syncing route status for job {job_id}: {str(e)}")
        # We don't want a sync failure to break the main job update API call
