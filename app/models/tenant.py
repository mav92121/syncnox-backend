from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    plan_type = Column(String, nullable=True)

    users = relationship("User", back_populates="tenant")
