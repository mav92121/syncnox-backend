from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.models.job import JobStatus, JobType, PriorityLevel, RecurrenceType, PaymentStatus
from app.schemas.common import Location

class JobBase(BaseModel):
    status: Optional[JobStatus] = None
    scheduled_date: Optional[date] = None
    job_type: Optional[JobType] = None
    location: Optional[Location] = None
    address_formatted: Optional[str] = None
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    service_duration: Optional[int] = None
    priority_level: Optional[PriorityLevel] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    customer_preferences: Optional[Dict[str, Any]] = None
    additional_notes: Optional[str] = None
    recurrence_type: Optional[RecurrenceType] = RecurrenceType.one_time
    documents: Optional[List[Dict[str, Any]]] = None
    payment_status: Optional[PaymentStatus] = None
    pod_notes: Optional[str] = None

class JobCreate(JobBase):
    pass

class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    scheduled_date: Optional[date] = None
    job_type: Optional[JobType] = None
    location: Optional[Location] = None
    address_formatted: Optional[str] = None
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    service_duration: Optional[int] = None
    priority_level: Optional[PriorityLevel] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    customer_preferences: Optional[Dict[str, Any]] = None
    additional_notes: Optional[str] = None
    recurrence_type: Optional[RecurrenceType] = None
    documents: Optional[List[Dict[str, Any]]] = None
    payment_status: Optional[PaymentStatus] = None
    pod_notes: Optional[str] = None

class JobResponse(JobBase):
    id: int

    class Config:
        from_attributes = True
