from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import engine, Base, get_db
from app.models.tenant import Tenant
from app.models.depot import Depot
from app.models.vehicle import Vehicle
from app.models.team_member import TeamMember
from app.models.job import Job
from app.models.route import Route, RouteStop
from app.models.user import User
from app.models.optimization_request import OptimizationRequest
from app.routers import auth, admin, team_member, depot, vehicle, job, optimization
from app.core.logging_config import logger

# Comment out Base.metadata.create_all as we're using Alembic for migrations
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SyncNox Route Optimization API", 
    version="1.0.0",
    redirect_slashes=False  # Disable automatic redirects to prevent POST data loss
)

# Configure CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.syncnox.com"],  # TODO: Restrict to specific origins in production (REQUIRED for cookie auth)
    allow_credentials=True,  # Required for HTTP-only cookie authentication
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(team_member.router, prefix="/api/team-members", tags=["Team Members"])
app.include_router(depot.router, prefix="/api/depots", tags=["Depots"])
app.include_router(vehicle.router, prefix="/api/vehicles", tags=["Vehicles"])
app.include_router(job.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(optimization.router, prefix="/api/optimization", tags=["Optimization"])


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )
