import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.database import SessionLocal
from app.models.tenant import Tenant
from app.models.team_member import TeamMember, TeamMemberRole

client = TestClient(app)


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
    tenant = Tenant(name="Test Driver Auth Tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # 2. Create a test driver
    driver = TeamMember(
        tenant_id=tenant.id,
        name="John Doe",
        role_type=TeamMemberRole.driver,
        email="john.doe.driver@example.com"
    )
    db_session.add(driver)
    
    # 3. Create a non-driver team member
    manager = TeamMember(
        tenant_id=tenant.id,
        name="Jane Manager",
        role_type=TeamMemberRole.manager,
        email="jane.manager@example.com"
    )
    db_session.add(manager)
    
    db_session.commit()
    db_session.refresh(driver)
    db_session.refresh(manager)

    yield {
        "tenant": tenant,
        "driver": driver,
        "manager": manager
    }

    # Cleanup
    db_session.delete(driver)
    db_session.delete(manager)
    db_session.delete(tenant)
    db_session.commit()


def test_activate_driver_success(test_data):
    driver_id = test_data["driver"].id
    
    # Test with /api/driver prefix
    response = client.post(f"/api/driver/{driver_id}/activate")
    assert response.status_code == 200
    data = response.json()
    assert "activation_code" in data
    code = data["activation_code"]
    
    # Verify code is exactly 12 numeric digits
    assert len(code) == 12
    assert code.isdigit()

    # Test with /driver prefix (alternative mount point)
    response_alt = client.post(f"/driver/{driver_id}/activate")
    assert response_alt.status_code == 200
    data_alt = response_alt.json()
    assert "activation_code" in data_alt
    assert len(data_alt["activation_code"]) == 12
    assert data_alt["activation_code"].isdigit()


def test_activate_non_existent_driver():
    response = client.post("/api/driver/999999/activate")
    assert response.status_code == 404
    assert response.json()["detail"] == "Driver not found"


def test_activate_non_driver_role(test_data):
    manager_id = test_data["manager"].id
    response = client.post(f"/api/driver/{manager_id}/activate")
    assert response.status_code == 404
    assert response.json()["detail"] == "Driver not found"


def test_verify_driver_success(test_data):
    driver_id = test_data["driver"].id
    
    # First, generate code
    activate_resp = client.post(f"/api/driver/{driver_id}/activate")
    assert activate_resp.status_code == 200
    code = activate_resp.json()["activation_code"]
    
    # Verify with /api/driver prefix using 'activation-code' header
    headers = {"activation-code": code}
    verify_resp = client.post("/api/driver/verify", headers=headers)
    assert verify_resp.status_code == 200
    driver_info = verify_resp.json()
    assert driver_info["id"] == driver_id
    assert driver_info["name"] == "John Doe"
    assert driver_info["email"] == "john.doe.driver@example.com"
    assert driver_info["activation_code"] == code

    # Verify with /driver prefix using 'x-activation-code' header (alternative name/prefix)
    headers_alt = {"x-activation-code": code}
    verify_resp_alt = client.post("/driver/verify", headers=headers_alt)
    assert verify_resp_alt.status_code == 200
    assert verify_resp_alt.json()["id"] == driver_id


def test_verify_driver_missing_header():
    response = client.post("/api/driver/verify")
    assert response.status_code == 400
    assert "required" in response.json()["detail"]


def test_verify_driver_invalid_code():
    headers = {"activation-code": "000000000000"}
    response = client.post("/api/driver/verify", headers=headers)
    assert response.status_code == 404
    assert "Invalid activation code" in response.json()["detail"]
