import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Time, Enum, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

class TeamMemberStatus(str,enum.Enum):
    active = "active"
    inactive = "inactive"
    online = "online"
    offline = "offline"

class TeamMemberRole(str,enum.Enum):
    admin = "admin"
    driver = "driver"
    manager = "manager"
    

class TeamMember(Base):
    __tablename__ = "team_member"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"), nullable=True)
    status = Column(Enum(TeamMemberStatus), nullable=True)
    name = Column(String, nullable=False)
    role_type = Column(Enum(TeamMemberRole), default="driver")
    external_identifier = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    navigation_link_format = Column(String, default="google_maps")
    work_start_time = Column(Time, nullable=True)
    work_end_time = Column(Time, nullable=True)
    allowed_overtime = Column(Boolean, default=False)
    max_distance = Column(Float, nullable=True)
    break_time_start = Column(Time, nullable=True)
    break_time_end = Column(Time, nullable=True)
    skills = Column(ARRAY(String), nullable=True)
    fixed_cost_for_driver = Column(Float, nullable=True)
    cost_per_km = Column(Float, nullable=True)
    cost_per_hr = Column(Float, nullable=True)
    cost_per_hr_overtime = Column(Float, nullable=True)
