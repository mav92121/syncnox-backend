import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin


class RouteAssignmentStatus(str, enum.Enum):
    pending = "pending"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    completed = "completed"


class RouteAssignment(Base, TimestampMixin):
    """
    Tracks which route has been dispatched to which driver, and the current
    acknowledgement / progress status on the driver's side.

    One row per (route, driver) pair. Re-sharing updates shared_at and resets
    status to 'pending' via INSERT ... ON CONFLICT DO UPDATE in the service layer.
    """
    __tablename__ = "route_assignment"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("route.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("team_member.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(
        Enum(RouteAssignmentStatus),
        nullable=False,
        default=RouteAssignmentStatus.pending,
        index=True,
    )
    shared_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    route = relationship("Route")
    driver = relationship("TeamMember")

    __table_args__ = (
        UniqueConstraint("route_id", "driver_id", name="uq_route_assignment_route_driver"),
    )
