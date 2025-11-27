from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from app.database import Base, TimestampMixin

class Depot(Base, TimestampMixin):
    __tablename__ = "depot"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(Geometry("POINT"), nullable=True)
    address = Column(JSONB, nullable=True)
