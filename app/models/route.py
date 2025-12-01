from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base, TimestampMixin

class Route(Base, TimestampMixin):
    __tablename__ = "route"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("team_member.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"), nullable=True)
    depot_id = Column(Integer, ForeignKey("depot.id"), nullable=True)
    optimization_request_id = Column(Integer, ForeignKey("optimization_request.id"), nullable=True)
    status = Column(String, nullable=True)
    scheduled_date = Column(Date, nullable=True)
    total_distance_meters = Column(Float, nullable=True)
    total_duration_seconds = Column(Float, nullable=True)
    route_polyline = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    additional_notes = Column(String, nullable=True)

    stops = relationship("RouteStop", back_populates="route")

class RouteStop(Base, TimestampMixin):
    __tablename__ = "route_stop"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("route.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job.id"), nullable=True)
    sequence_order = Column(Integer, nullable=True)
    stop_type = Column(String, nullable=True)
    planned_arrival_time = Column(DateTime, nullable=True)
    planned_departure_time = Column(DateTime, nullable=True)
    estimated_distance_from_prev = Column(Float, nullable=True)
    actual_arrival_time = Column(DateTime, nullable=True)
    actual_departure_time = Column(DateTime, nullable=True)
    geofence_entered_at = Column(DateTime, nullable=True)

    route = relationship("Route", back_populates="stops")
