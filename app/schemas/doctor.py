from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class DoctorScheduleCreate(BaseModel):
    day_of_week: str = Field(..., pattern=r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")


class DoctorScheduleResponse(BaseModel):
    id: str
    day_of_week: str
    start_time: str
    end_time: str
    is_active: bool

    class Config:
        from_attributes = True


class DoctorProfileResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    specialization: str
    consultation_duration_minutes: int
    is_available: bool
    schedules: list[DoctorScheduleResponse] = []

    class Config:
        from_attributes = True


class DoctorListResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    specialization: str
    is_available: bool

    class Config:
        from_attributes = True


class DoctorAvailabilityUpdate(BaseModel):
    is_available: bool
