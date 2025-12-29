import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from app.database import Base, TimestampMixin

class VehicleType(str, enum.Enum):
    car = "car"
    small_truck = "small_truck"
    truck = "truck"
    scooter = "scooter"
    foot = "foot"
    bike = "bike"
    mountain_bike = "mountain_bike"

class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicle"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    team_member_id = Column(Integer, ForeignKey("team_member.id"), nullable=True)
    name = Column(String, nullable=False)
    capacity_weight = Column(Float, nullable=True)
    capacity_volume = Column(Float, nullable=True)
    type = Column(Enum(VehicleType), nullable=True)
    license_plate = Column(String, nullable=True)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
