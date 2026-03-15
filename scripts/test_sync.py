import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.route import Route, RouteStatus
from app.models.optimization_request import OptimizationRequest
from app.services.status_sync import sync_route_status_for_job

def test_sync():
    print("Starting test sync...")
    db: Session = SessionLocal()
    try:
        # Find a job that is part of a route
        # This assumes there is at least some data in the database
        route = db.query(Route).filter(Route.stops.any()).first()
        if not route:
            print("No routes with stops found. Cannot test without seed data.")
            return
            
        print(f"Testing with route {route.id}")
        
        # Get a job from this route
        stop = None
        for s in route.stops:
            if s.stop_type == 'job' and s.job_id:
                stop = s
                break
                
        if not stop:
            print("No job stops found in this route.")
            return
            
        job = db.query(Job).get(stop.job_id)
        if not job:
            print("Job not found.")
            return
            
        print(f"Found job {job.id} with status {job.status}. Setting to IN_TRANSIT.")
        
        # Test 1: Set job to IN_TRANSIT
        job.status = JobStatus.in_transit
        db.commit()
        
        sync_route_status_for_job(db, job.id)
        
        # Refresh models
        db.refresh(route)
        opt_req = db.query(OptimizationRequest).get(route.optimization_request_id) if route.optimization_request_id else None
        
        print("\n--- After setting one job to IN_TRANSIT ---")
        print(f"Route Status: {route.status}")
        if opt_req:
            print(f"OptimizationRequest Status: {opt_req.route_status}")
            
        print(f"Expected: {RouteStatus.in_transit}")
        
        # Optional: Reset back to previous state if this is production
        # But this is likely a local test DB. Let's just demonstrate the code works.

    finally:
        db.close()

if __name__ == "__main__":
    test_sync()
