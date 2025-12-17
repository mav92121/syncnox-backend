from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from app.models.job import JobStatus, JobType, PriorityLevel, RecurrenceType, PaymentStatus
from app.schemas.common import Location

class JobBase(BaseModel):
    assigned_to: Optional[int] = None
    status: Optional[JobStatus] = None
    scheduled_date: Optional[date] = None
    job_type: Optional[JobType] = None
    location: Optional[Location] = None
    address_formatted: Optional[str] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    service_duration: Optional[int] = None
    priority_level: Optional[PriorityLevel] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    customer_preferences: Optional[str] = None
    additional_notes: Optional[str] = None
    recurrence_type: Optional[RecurrenceType] = RecurrenceType.one_time
    documents: Optional[List[Dict[str, Any]]] = None
    payment_status: Optional[PaymentStatus] = None
    pod_notes: Optional[str] = None

class JobCreate(JobBase):
    pass

class JobUpdate(BaseModel):
    assigned_to: Optional[int] = None
    status: Optional[JobStatus] = None
    scheduled_date: Optional[date] = None
    job_type: Optional[JobType] = None
    location: Optional[Location] = None
    address_formatted: Optional[str] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    service_duration: Optional[int] = None
    priority_level: Optional[PriorityLevel] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    customer_preferences: Optional[str] = None
    additional_notes: Optional[str] = None
    recurrence_type: Optional[RecurrenceType] = None
    documents: Optional[List[Dict[str, Any]]] = None
    payment_status: Optional[PaymentStatus] = None
    pod_notes: Optional[str] = None

class JobResponse(JobBase):
    id: int
    tenant_id: int
    route_name: Optional[str] = None
    optimization_id: Optional[int] = None

    class Config:
        from_attributes = True

    @field_validator("location", mode="before")
    @classmethod
    def serialize_location(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return {"lat": shape.y, "lng": shape.x}
        return v
