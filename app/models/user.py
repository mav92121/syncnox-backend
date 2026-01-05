from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="users")
