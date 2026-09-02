from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
from app.models import UserRole
import re


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class PatientRegister(UserRegister):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    phone: str = Field(..., pattern=r"^\+?[\d\s-]{10,20}$")
    insurance_number: Optional[str] = None


class DoctorCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    specialization: str = Field(..., min_length=1, max_length=100)
    license_number: str = Field(..., min_length=1, max_length=50)
    consultation_duration_minutes: int = Field(default=30, ge=15, le=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)
    
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
