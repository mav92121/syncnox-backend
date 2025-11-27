from sqlalchemy import Column, Integer, String
from app.database import Base, TimestampMixin

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    plan_type = Column(String, nullable=True)
