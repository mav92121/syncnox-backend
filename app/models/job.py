import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Date, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from app.database import Base, TimestampMixin

class JobStatus(str, enum.Enum):
    draft = "draft"
    assigned = "assigned"
    completed = "completed"
    in_transit = "in_transit"

class JobType(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"
    service = "service"

class PriorityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RecurrenceType(str, enum.Enum):
    one_time = "one_time"
    recurring = "recurring"

class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"

class Job(Base, TimestampMixin):
    __tablename__ = "job"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("team_member.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("route.id"), nullable=True)
    status = Column(Enum(JobStatus), nullable=True, default=JobStatus.draft)
    scheduled_date = Column(Date, nullable=True)
    job_type = Column(Enum(JobType), nullable=True)
    location = Column(Geometry("POINT"), nullable=True)
    address_formatted = Column(String, nullable=True)
    time_window_start = Column(String, nullable=True)
    time_window_end = Column(String, nullable=True)
    service_duration = Column(Integer, nullable=True) # in mins
    priority_level = Column(Enum(PriorityLevel), nullable=True, default=PriorityLevel.medium)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    customer_preferences = Column(String, nullable=True)
    additional_notes = Column(String, nullable=True)
    recurrence_type = Column(Enum(RecurrenceType), nullable=True, default=RecurrenceType.one_time)
    documents = Column(JSONB, nullable=True) # list of docs
    payment_status = Column(Enum(PaymentStatus), nullable=True, default=PaymentStatus.paid)
    pod_notes = Column(String, nullable=True) # proof of delivery notes

    route = relationship("Route")

    @property
    def route_name(self):
        if self.route and self.route.optimization_request:
            return self.route.optimization_request.route_name
        return None

    @property
    def optimization_id(self):
        if self.route:
            return self.route.optimization_request_id
        return None
