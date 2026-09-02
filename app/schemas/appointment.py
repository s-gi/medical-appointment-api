from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from app.models import AppointmentStatus


class AppointmentCreate(BaseModel):
    doctor_id: str
    appointment_datetime: datetime
    reason: Optional[str] = Field(None, max_length=500)
    
    @field_validator("appointment_datetime")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        if v <= datetime.utcnow():
            raise ValueError("Appointment must be in the future")
        return v


class AppointmentUpdate(BaseModel):
    appointment_datetime: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=500)
    
    @field_validator("appointment_datetime")
    @classmethod
    def validate_future_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v <= datetime.utcnow():
            raise ValueError("Appointment must be in the future")
        return v


class AppointmentCancel(BaseModel):
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class DoctorNotesUpdate(BaseModel):
    notes: str = Field(..., max_length=2000)


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    appointment_datetime: datetime
    end_datetime: datetime
    status: AppointmentStatus
    reason: Optional[str] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    id: str
    doctor_name: str
    patient_name: Optional[str] = None  # Only visible to doctors/admins
    appointment_datetime: datetime
    end_datetime: datetime
    status: AppointmentStatus
    specialization: str


class AvailableSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    doctor_id: str
    doctor_name: str
    specialization: str
