import pytest
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models.tenant import Tenant
from app.models.team_member import TeamMember, TeamMemberRole
from app.models.optimization_request import OptimizationRequest, OptimizationStatus, OptimizationGoal
from app.models.route import Route, RouteStatus
from app.models.route_assignment import RouteAssignment, RouteAssignmentStatus
from app.services.route_sharing import route_sharing_service


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_data(db_session: Session):
    # 1. Create a test tenant
    tenant = Tenant(name="Test Route Sharing Tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # 2. Create a test driver
    driver = TeamMember(
        tenant_id=tenant.id,
        name="Route Driver",
        role_type=TeamMemberRole.driver,
        email="route.driver@example.com"
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)

    # 3. Create two optimization requests (we need depot_id=1, but let's see if depot is foreign key)
    # Wait, depot_id has ForeignKey("depot.id"), so we need to create a test depot or mock it.
    # Let's import Depot and create one first!
    from app.models.depot import Depot
    depot = Depot(
        tenant_id=tenant.id,
        name="Test Depot",
        address="123 Test St",
        location="POINT(0 0)"
    )
    db_session.add(depot)
    db_session.commit()
    db_session.refresh(depot)

    opt1 = OptimizationRequest(
        tenant_id=tenant.id,
        route_name="Opt 1",
        depot_id=depot.id,
        job_ids=[],
        team_member_ids=[driver.id],
        scheduled_date=date.today(),
        optimization_goal=OptimizationGoal.MINIMUM_TIME,
        status=OptimizationStatus.COMPLETED
    )
    db_session.add(opt1)

    opt2 = OptimizationRequest(
        tenant_id=tenant.id,
        route_name="Opt 2",
        depot_id=depot.id,
        job_ids=[],
        team_member_ids=[driver.id],
        scheduled_date=date.today(),
        optimization_goal=OptimizationGoal.MINIMUM_TIME,
        status=OptimizationStatus.COMPLETED
    )
    db_session.add(opt2)
    db_session.commit()
    db_session.refresh(opt1)
    db_session.refresh(opt2)

    # 4. Create two routes
    route1 = Route(
        tenant_id=tenant.id,
        driver_id=driver.id,
        optimization_request_id=opt1.id,
        status=RouteStatus.scheduled,
        scheduled_date=date.today()
    )
    db_session.add(route1)

    route2 = Route(
        tenant_id=tenant.id,
        driver_id=driver.id,
        optimization_request_id=opt2.id,
        status=RouteStatus.scheduled,
        scheduled_date=date.today()
    )
    db_session.add(route2)
    db_session.commit()
    db_session.refresh(route1)
    db_session.refresh(route2)

    yield {
        "tenant": tenant,
        "driver": driver,
        "depot": depot,
        "opt1": opt1,
        "opt2": opt2,
        "route1": route1,
        "route2": route2
    }

    # Cleanup
    # Delete route assignments first to prevent foreign key errors
    db_session.query(RouteAssignment).filter(RouteAssignment.tenant_id == tenant.id).delete()
    db_session.delete(route1)
    db_session.delete(route2)
    db_session.commit()

    db_session.delete(opt1)
    db_session.delete(opt2)
    db_session.commit()

    db_session.delete(depot)
    db_session.delete(driver)
    db_session.delete(tenant)
    db_session.commit()


def test_share_multiple_routes_to_same_driver(db_session: Session, test_data):
    driver = test_data["driver"]
    tenant = test_data["tenant"]
    opt1 = test_data["opt1"]
    opt2 = test_data["opt2"]
    route1 = test_data["route1"]
    route2 = test_data["route2"]

    # 1. Share first route
    res1 = route_sharing_service.share_optimization_routes(
        db=db_session,
        optimization_request_id=opt1.id,
        tenant_id=tenant.id
    )
    assert driver.id in res1["driver_ids"]

    # Check assignment status
    assignment1 = db_session.execute(
        select(RouteAssignment).where(
            RouteAssignment.route_id == route1.id,
            RouteAssignment.driver_id == driver.id
        )
    ).scalar_one()
    assert assignment1.status == RouteAssignmentStatus.pending

    # Get driver route — should return route1
    driver_route_data = route_sharing_service.get_driver_route(db=db_session, driver_id=driver.id)
    assert driver_route_data["route"].id == route1.id
    assert driver_route_data["assignment_status"] == RouteAssignmentStatus.pending.value

    # Acknowledge the first route
    ack_res = route_sharing_service.acknowledge_route(db=db_session, driver_id=driver.id)
    assert ack_res.status == RouteAssignmentStatus.acknowledged

    # 2. Share second route
    res2 = route_sharing_service.share_optimization_routes(
        db=db_session,
        optimization_request_id=opt2.id,
        tenant_id=tenant.id
    )
    assert driver.id in res2["driver_ids"]

    # Refresh first assignment from DB and check that it was marked as completed
    db_session.refresh(assignment1)
    assert assignment1.status == RouteAssignmentStatus.completed
    assert assignment1.completed_at is not None

    # Check assignment status for route2
    assignment2 = db_session.execute(
        select(RouteAssignment).where(
            RouteAssignment.route_id == route2.id,
            RouteAssignment.driver_id == driver.id
        )
    ).scalar_one()
    assert assignment2.status == RouteAssignmentStatus.pending

    # Get driver route — should now return route2 without raising MultipleResultsFound
    driver_route_data_2 = route_sharing_service.get_driver_route(db=db_session, driver_id=driver.id)
    assert driver_route_data_2["route"].id == route2.id
    assert driver_route_data_2["assignment_status"] == RouteAssignmentStatus.pending.value

    # Acknowledge second route without raising MultipleResultsFound
    ack_res_2 = route_sharing_service.acknowledge_route(db=db_session, driver_id=driver.id)
    assert ack_res_2.status == RouteAssignmentStatus.acknowledged
