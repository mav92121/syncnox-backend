import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Date, Enum
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
    status = Column(Enum(JobStatus), nullable=True, default=JobStatus.draft)
    scheduled_date = Column(Date, nullable=True)
    job_type = Column(Enum(JobType), nullable=True)
    location = Column(Geometry("POINT"), nullable=True)
    address_formatted = Column(String, nullable=True)
    time_window_start = Column(DateTime, nullable=True)
    time_window_end = Column(DateTime, nullable=True)
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
