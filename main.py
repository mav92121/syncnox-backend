from fastapi import FastAPI
from app.database import engine, Base
from app.models.tenant import Tenant
from app.models.depot import Depot
from app.models.vehicle import Vehicle
from app.models.team_member import TeamMember
from app.models.job import Job
from app.models.route import Route, RouteStop

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/health")
async def health_check():
    return {
        "status": "success"
    }
