from .auth import (
    UserRegister,
    PatientRegister,
    DoctorCreate,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    PasswordChangeRequest,
)
from .appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentCancel,
    DoctorNotesUpdate,
    AppointmentResponse,
    AppointmentListResponse,
    AvailableSlot,
)
from .doctor import (
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    DoctorProfileResponse,
    DoctorListResponse,
    DoctorAvailabilityUpdate,
)

__all__ = [
    "UserRegister",
    "PatientRegister",
    "DoctorCreate",
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "UserResponse",
    "PasswordChangeRequest",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentCancel",
    "DoctorNotesUpdate",
    "AppointmentResponse",
    "AppointmentListResponse",
    "AvailableSlot",
    "DoctorScheduleCreate",
    "DoctorScheduleResponse",
    "DoctorProfileResponse",
    "DoctorListResponse",
    "DoctorAvailabilityUpdate",
]
