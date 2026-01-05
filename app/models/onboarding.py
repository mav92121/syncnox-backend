from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin


class Onboarding(Base, TimestampMixin):
    """
    Tracks onboarding progress for each tenant.
    Uses tenant_id as primary key (1:1 relationship with tenant).
    """
    __tablename__ = "onboarding"

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    current_step = Column(Integer, default=0, nullable=False)  # 0=welcome, 1=basic, 2=depot, 3=fleet, 4=team
    company_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)

    tenant = relationship("Tenant", back_populates="onboarding")
