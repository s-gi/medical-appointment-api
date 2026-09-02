from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, UserRole, DoctorProfile, DoctorSchedule
from app.schemas import (
    DoctorCreate,
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    DoctorProfileResponse,
    DoctorListResponse,
    DoctorAvailabilityUpdate,
)
from app.security import hash_password, encrypt_data
from app.auth import get_current_user, require_admin, require_doctor, get_client_ip, get_user_agent
from app.utils import log_action

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=list[DoctorListResponse])
async def list_doctors(
    specialization: str | None = None,
    available_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all doctors (public endpoint)."""
    query = select(DoctorProfile)
    
    if available_only:
        query = query.where(DoctorProfile.is_available == True)
    
    if specialization:
        query = query.where(DoctorProfile.specialization.ilike(f"%{specialization}%"))
    
    result = await db.execute(query)
    doctors = result.scalars().all()
    
    return [
        DoctorListResponse(
            id=doc.id,
            first_name=doc.first_name,
            last_name=doc.last_name,
            specialization=doc.specialization,
            is_available=doc.is_available,
        )
        for doc in doctors
    ]


@router.get("/{doctor_id}", response_model=DoctorProfileResponse)
async def get_doctor(
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get doctor details with schedule."""
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
    
    return DoctorProfileResponse(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialization=doctor.specialization,
        consultation_duration_minutes=int(doctor.consultation_duration_minutes),
        is_available=doctor.is_available,
        schedules=[
            DoctorScheduleResponse(
                id=s.id,
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                is_active=s.is_active,
            )
            for s in doctor.schedules if s.is_active
        ],
    )


@router.post("", response_model=DoctorProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    data: DoctorCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new doctor (admin only)."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create user
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role=UserRole.DOCTOR,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    
    # Create doctor profile
    doctor_profile = DoctorProfile(
        user_id=user.id,
        first_name=data.first_name,
        last_name=data.last_name,
        specialization=data.specialization,
        license_number_encrypted=encrypt_data(data.license_number),
        consultation_duration_minutes=str(data.consultation_duration_minutes),
    )
    db.add(doctor_profile)
    await db.flush()
    
    await log_action(
        db=db,
        action="DOCTOR_CREATED",
        resource_type="doctor",
        resource_id=doctor_profile.id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return DoctorProfileResponse(
        id=doctor_profile.id,
        first_name=doctor_profile.first_name,
        last_name=doctor_profile.last_name,
        specialization=doctor_profile.specialization,
        consultation_duration_minutes=int(doctor_profile.consultation_duration_minutes),
        is_available=doctor_profile.is_available,
        schedules=[],
    )


@router.post("/{doctor_id}/schedules", response_model=DoctorScheduleResponse, status_code=status.HTTP_201_CREATED)
async def add_doctor_schedule(
    doctor_id: str,
    data: DoctorScheduleCreate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Add schedule for a doctor (doctor or admin)."""
    # Verify doctor exists and user has permission
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.id == doctor_id)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )
    
    # Only allow doctor to edit their own schedule (or admin)
    if current_user.role != UserRole.ADMIN and doctor.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another doctor's schedule",
        )
    
    schedule = DoctorSchedule(
        doctor_id=doctor_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    db.add(schedule)
    await db.flush()
    
    await log_action(
        db=db,
        action="SCHEDULE_CREATED",
        resource_type="schedule",
        resource_id=schedule.id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return schedule


@router.patch("/{doctor_id}/availability", response_model=DoctorProfileResponse)
async def update_doctor_availability(
    doctor_id: str,
    data: DoctorAvailabilityUpdate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update doctor availability (doctor or admin)."""
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
    
    if current_user.role != UserRole.ADMIN and doctor.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another doctor's availability",
        )
    
    doctor.is_available = data.is_available
    
    await log_action(
        db=db,
        action="AVAILABILITY_UPDATED",
        resource_type="doctor",
        resource_id=doctor_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        details=f"Available: {data.is_available}",
    )
    
    return DoctorProfileResponse(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialization=doctor.specialization,
        consultation_duration_minutes=int(doctor.consultation_duration_minutes),
        is_available=doctor.is_available,
        schedules=[
            DoctorScheduleResponse(
                id=s.id,
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                is_active=s.is_active,
            )
            for s in doctor.schedules if s.is_active
        ],
    )


@router.delete("/{doctor_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor_schedule(
    doctor_id: str,
    schedule_id: str,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Delete a doctor's schedule (doctor or admin)."""
    result = await db.execute(
        select(DoctorSchedule)
        .join(DoctorProfile)
        .where(DoctorSchedule.id == schedule_id, DoctorSchedule.doctor_id == doctor_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    
    # Check permission
    doctor_result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.id == doctor_id)
    )
    doctor = doctor_result.scalar_one_or_none()
    
    if current_user.role != UserRole.ADMIN and doctor.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another doctor's schedule",
        )
    
    schedule.is_active = False
    
    await log_action(
        db=db,
        action="SCHEDULE_DELETED",
        resource_type="schedule",
        resource_id=schedule_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
