from app.database import SessionLocal, engine, Base
from app.models.tenant import Tenant
from app.models.depot import Depot
from app.models.vehicle import Vehicle
from app.models.team_member import TeamMember
from app.models.job import Job
from app.models.route import Route, RouteStop
from sqlalchemy import text
import datetime

def test_models():
    db = SessionLocal()
    try:
        # Create a tenant
        tenant = Tenant(name="Test Tenant", plan_type="Basic")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print(f"Created Tenant: {tenant.id} - {tenant.name}")

        # Create a depot
        depot = Depot(tenant_id=tenant.id, name="Main Depot", location="POINT(0 0)", address={"city": "New York"})
        db.add(depot)
        db.commit()
        print(f"Created Depot: {depot.name}")

        # Create a vehicle
        vehicle = Vehicle(tenant_id=tenant.id, name="Truck 1", type="truck")
        db.add(vehicle)
        db.commit()
        print(f"Created Vehicle: {vehicle.name}")

        # Create a team member (driver)
        driver = TeamMember(tenant_id=tenant.id, name="John Doe", vehicle_id=vehicle.id)
        db.add(driver)
        db.commit()
        print(f"Created TeamMember: {driver.name}")

        # Create a job
        job = Job(tenant_id=tenant.id, status="draft", scheduled_date=datetime.date.today())
        db.add(job)
        db.commit()
        print(f"Created Job: {job.id}")

        # Create a route
        route = Route(tenant_id=tenant.id, driver_id=driver.id, vehicle_id=vehicle.id, depot_id=depot.id)
        db.add(route)
        db.commit()
        print(f"Created Route: {route.id}")

        # Create a route stop
        stop = RouteStop(route_id=route.id, job_id=job.id, sequence_order=1)
        db.add(stop)
        db.commit()
        print(f"Created RouteStop: {stop.id}")

        print("All models verified successfully!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Enable PostGIS extension
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.commit()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    test_models()
