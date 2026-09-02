from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import User, UserRole, AuditLog, Appointment, AppointmentStatus
from app.schemas import UserResponse
from app.auth import require_admin, get_client_ip, get_user_agent
from app.utils import log_action

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    query = select(User)
    
    if role:
        query = query.where(User.role == role)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user account (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.is_active = False
    
    await log_action(
        db=db,
        action="USER_DEACTIVATED",
        resource_type="user",
        resource_id=user_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return {"message": "User deactivated successfully"}


@router.patch("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Activate a user account (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.is_active = True
    user.locked_until = None
    
    await log_action(
        db=db,
        action="USER_ACTIVATED",
        resource_type="user",
        resource_id=user_id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return {"message": "User activated successfully"}


@router.get("/audit-logs")
async def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    from_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs (admin only)."""
    query = select(AuditLog)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    
    if from_date:
        query = query.where(AuditLog.created_at >= datetime.strptime(from_date, "%Y-%m-%d"))
    
    if to_date:
        query = query.where(AuditLog.created_at <= datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1))
    
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/stats")
async def get_statistics(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get system statistics (admin only)."""
    # Count users by role
    users_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = {role.value: count for role, count in users_result.all()}
    
    # Count appointments by status
    appointments_result = await db.execute(
        select(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status)
    )
    appointments_by_status = {status.value: count for status, count in appointments_result.all()}
    
    # Today's appointments
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    today_end = datetime.combine(datetime.utcnow().date(), datetime.max.time())
    
    today_result = await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.appointment_datetime.between(today_start, today_end)
        )
    )
    today_appointments = today_result.scalar() or 0
    
    # This week's appointments
    week_start = today_start - timedelta(days=datetime.utcnow().weekday())
    week_end = week_start + timedelta(days=7)
    
    week_result = await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.appointment_datetime.between(week_start, week_end)
        )
    )
    week_appointments = week_result.scalar() or 0
    
    return {
        "users_by_role": users_by_role,
        "appointments_by_status": appointments_by_status,
        "today_appointments": today_appointments,
        "this_week_appointments": week_appointments,
    }
