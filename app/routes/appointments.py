from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import User, UserRole, PatientProfile, DoctorProfile, Appointment, AppointmentStatus, DoctorSchedule
from app.schemas import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentCancel,
    DoctorNotesUpdate,
    AppointmentResponse,
    AppointmentListResponse,
    AvailableSlot,
)
from app.security import encrypt_data, decrypt_data
from app.auth import get_current_user, require_doctor, get_client_ip, get_user_agent
from app.utils import log_action

router = APIRouter(prefix="/appointments", tags=["Appointments"])


async def get_patient_profile(user: User, db: AsyncSession) -> PatientProfile:
    """Get patient profile for current user."""
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    return patient


async def get_doctor_profile(user: User, db: AsyncSession) -> DoctorProfile:
    """Get doctor profile for current user."""
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )
    return doctor


@router.get("/available-slots", response_model=list[AvailableSlot])
async def get_available_slots(
    doctor_id: str,
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    """Get available appointment slots for a doctor on a specific date."""
    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format",
        )
    
    if target_date < datetime.utcnow().date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book appointments in the past",
        )
    
    # Get doctor with schedules
    result = await db.execute(
        select(DoctorProfile)
        .options(selectinload(DoctorProfile.schedules))
        .where(DoctorProfile.id == doctor_id)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )
    
    if not doctor.is_available:
        return []
    
    # Get day of week
    day_of_week = target_date.strftime("%A").lower()
    
    # Find matching schedule
    schedule = None
    for s in doctor.schedules:
        if s.day_of_week == day_of_week and s.is_active:
            schedule = s
            break
    
    if not schedule:
        return []
    
    # Get existing appointments for that day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    appointments_result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_datetime >= start_of_day,
                Appointment.appointment_datetime <= end_of_day,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            )
        )
    )
    existing_appointments = appointments_result.scalars().all()
    
    # Generate available slots
    consultation_duration = int(doctor.consultation_duration_minutes)
    start_time = datetime.combine(target_date, datetime.strptime(schedule.start_time, "%H:%M").time())
    end_time = datetime.combine(target_date, datetime.strptime(schedule.end_time, "%H:%M").time())
    
    slots = []
    current_slot = start_time
    
    while current_slot + timedelta(minutes=consultation_duration) <= end_time:
        slot_end = current_slot + timedelta(minutes=consultation_duration)
        
        # Check if slot conflicts with existing appointments
        is_available = True
        for appt in existing_appointments:
            if not (slot_end <= appt.appointment_datetime or current_slot >= appt.end_datetime):
                is_available = False
                break
        
        # Don't show past slots for today
        if target_date == datetime.utcnow().date() and current_slot <= datetime.utcnow():
            is_available = False
        
        if is_available:
            slots.append(AvailableSlot(
                start_time=current_slot,
                end_time=slot_end,
                doctor_id=doctor.id,
                doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
                specialization=doctor.specialization,
            ))
        
        current_slot = slot_end
    
    return slots


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new appointment (patients only)."""
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can book appointments",
        )
    
    patient = await get_patient_profile(current_user, db)
    
    # Get doctor
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.id == data.doctor_id)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )
    
    if not doctor.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is not available for appointments",
        )
    
    # Calculate end time
    consultation_duration = int(doctor.consultation_duration_minutes)
    end_datetime = data.appointment_datetime + timedelta(minutes=consultation_duration)
    
    # Check for conflicts
    conflicts_result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.doctor_id == data.doctor_id,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                or_(
                    and_(
                        Appointment.appointment_datetime <= data.appointment_datetime,
                        Appointment.end_datetime > data.appointment_datetime,
                    ),
                    and_(
                        Appointment.appointment_datetime < end_datetime,
                        Appointment.end_datetime >= end_datetime,
                    ),
                ),
            )
        )
    )
    
    if conflicts_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This time slot is no longer available",
        )
    
    # Create appointment
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=data.doctor_id,
        appointment_datetime=data.appointment_datetime,
        end_datetime=end_datetime,
        reason_encrypted=encrypt_data(data.reason) if data.reason else None,
    )
    db.add(appointment)
    await db.flush()
    
    await log_action(
        db=db,
        action="APPOINTMENT_CREATED",
        resource_type="appointment",
        resource_id=appointment.id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=None,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.get("", response_model=list[AppointmentListResponse])
async def list_appointments(
    status_filter: Optional[AppointmentStatus] = None,
    from_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List appointments for current user."""
    query = select(Appointment).options(
        selectinload(Appointment.doctor),
        selectinload(Appointment.patient),
    )
    
    # Filter based on role
    if current_user.role == UserRole.PATIENT:
        patient = await get_patient_profile(current_user, db)
        query = query.where(Appointment.patient_id == patient.id)
    elif current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        query = query.where(Appointment.doctor_id == doctor.id)
    # Admin sees all
    
    if status_filter:
        query = query.where(Appointment.status == status_filter)
    
    if from_date:
        query = query.where(Appointment.appointment_datetime >= datetime.strptime(from_date, "%Y-%m-%d"))
    
    if to_date:
        query = query.where(Appointment.appointment_datetime <= datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1))
    
    query = query.order_by(Appointment.appointment_datetime.desc())
    
    result = await db.execute(query)
    appointments = result.scalars().all()
    
    response = []
    for appt in appointments:
        patient_name = None
        if current_user.role in [UserRole.DOCTOR, UserRole.ADMIN]:
            patient_name = f"{decrypt_data(appt.patient.first_name_encrypted)} {decrypt_data(appt.patient.last_name_encrypted)}"
        
        response.append(AppointmentListResponse(
            id=appt.id,
            doctor_name=f"Dr. {appt.doctor.first_name} {appt.doctor.last_name}",
            patient_name=patient_name,
            appointment_datetime=appt.appointment_datetime,
            end_datetime=appt.end_datetime,
            status=appt.status,
            specialization=appt.doctor.specialization,
        ))
    
    return response


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get appointment details."""
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.doctor), selectinload(Appointment.patient))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    
    # Check access permission
    has_access = False
    if current_user.role == UserRole.ADMIN:
        has_access = True
    elif current_user.role == UserRole.PATIENT:
        patient = await get_patient_profile(current_user, db)
        has_access = appointment.patient_id == patient.id
    elif current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        has_access = appointment.doctor_id == doctor.id
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Only doctors/admins can see notes
    notes = None
    if current_user.role in [UserRole.DOCTOR, UserRole.ADMIN] and appointment.notes_encrypted:
        notes = decrypt_data(appointment.notes_encrypted)
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=notes,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.patch("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: str,
    data: AppointmentCancel,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an appointment."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    
    # Check access permission
    has_access = False
    if current_user.role == UserRole.ADMIN:
        has_access = True
    elif current_user.role == UserRole.PATIENT:
        patient = await get_patient_profile(current_user, db)
        has_access = appointment.patient_id == patient.id
    elif current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        has_access = appointment.doctor_id == doctor.id
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    if appointment.status in [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel this appointment",
        )
    
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = data.cancellation_reason
    
    await log_action(
        db=db,
        action="APPOINTMENT_CANCELLED",
        resource_type="appointment",
        resource_id=appointment_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=None,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.patch("/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    appointment_id: str,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Confirm an appointment (doctor/admin only)."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    
    # Check doctor permission
    if current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        if appointment.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot confirm another doctor's appointment",
            )
    
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only confirm scheduled appointments",
        )
    
    appointment.status = AppointmentStatus.CONFIRMED
    
    await log_action(
        db=db,
        action="APPOINTMENT_CONFIRMED",
        resource_type="appointment",
        resource_id=appointment_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=None,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.patch("/{appointment_id}/complete", response_model=AppointmentResponse)
async def complete_appointment(
    appointment_id: str,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Mark appointment as completed (doctor/admin only)."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    
    if current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        if appointment.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot complete another doctor's appointment",
            )
    
    if appointment.status not in [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete this appointment",
        )
    
    appointment.status = AppointmentStatus.COMPLETED
    
    await log_action(
        db=db,
        action="APPOINTMENT_COMPLETED",
        resource_type="appointment",
        resource_id=appointment_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=decrypt_data(appointment.notes_encrypted) if appointment.notes_encrypted else None,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.patch("/{appointment_id}/notes", response_model=AppointmentResponse)
async def update_appointment_notes(
    appointment_id: str,
    data: DoctorNotesUpdate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update appointment notes (doctor/admin only)."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    
    if current_user.role == UserRole.DOCTOR:
        doctor = await get_doctor_profile(current_user, db)
        if appointment.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update notes for another doctor's appointment",
            )
    
    appointment.notes_encrypted = encrypt_data(data.notes)
    
    await log_action(
        db=db,
        action="APPOINTMENT_NOTES_UPDATED",
        resource_type="appointment",
        resource_id=appointment_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_datetime=appointment.appointment_datetime,
        end_datetime=appointment.end_datetime,
        status=appointment.status,
        reason=decrypt_data(appointment.reason_encrypted) if appointment.reason_encrypted else None,
        notes=decrypt_data(appointment.notes_encrypted),
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )
