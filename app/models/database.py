from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(String(10), default="0")
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False)
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="user")


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    first_name_encrypted = Column(Text, nullable=False)
    last_name_encrypted = Column(Text, nullable=False)
    date_of_birth_encrypted = Column(Text, nullable=False)
    phone_encrypted = Column(Text, nullable=False)
    insurance_number_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="patient_profile")
    appointments = relationship("Appointment", back_populates="patient")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False)
    license_number_encrypted = Column(Text, nullable=False)
    consultation_duration_minutes = Column(String(10), default="30")
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="doctor_profile")
    schedules = relationship("DoctorSchedule", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id"), nullable=False)
    day_of_week = Column(String(10), nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    is_active = Column(Boolean, default=True)

    doctor = relationship("DoctorProfile", back_populates="schedules")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patient_profiles.id"), nullable=False)
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id"), nullable=False)
    appointment_datetime = Column(DateTime, nullable=False, index=True)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    reason_encrypted = Column(Text, nullable=True)
    notes_encrypted = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("PatientProfile", back_populates="appointments")
    doctor = relationship("DoctorProfile", back_populates="appointments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="audit_logs")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)  # Keep unique for security
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
