from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, UserRole, PatientProfile
from app.schemas import (
    PatientRegister,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    PasswordChangeRequest,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    encrypt_data,
    decrypt_data,
)
from app.auth import get_current_user, get_client_ip, get_user_agent
from app.utils import log_action
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_patient(
    data: PatientRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new patient account."""
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role=UserRole.PATIENT,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    
    patient_profile = PatientProfile(
        user_id=user.id,
        first_name_encrypted=encrypt_data(data.first_name),
        last_name_encrypted=encrypt_data(data.last_name),
        date_of_birth_encrypted=encrypt_data(data.date_of_birth),
        phone_encrypted=encrypt_data(data.phone),
        insurance_number_encrypted=encrypt_data(data.insurance_number) if data.insurance_number else None,
    )
    db.add(patient_profile)
    
    await log_action(
        db=db,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    if user.locked_until and user.locked_until > datetime.utcnow():
        await log_action(
            db=db,
            action="LOGIN_ATTEMPT_LOCKED",
            resource_type="user",
            resource_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked. Please try again later.",
        )
    
    if not verify_password(data.password, user.hashed_password):
        try:
            current_attempts = int(decrypt_data(user.failed_login_attempts) or "0")
        except Exception:
            current_attempts = 0
        current_attempts += 1
        user.failed_login_attempts = encrypt_data(str(current_attempts))
        
        if current_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            await log_action(
                db=db,
                action="ACCOUNT_LOCKED",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                details=f"Locked after {current_attempts} failed attempts",
            )
        
        await log_action(
            db=db,
            action="LOGIN_FAILED",
            resource_type="user",
            resource_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    
    user.failed_login_attempts = encrypt_data("0")
    user.locked_until = None
    
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.role.value)
    
    await log_action(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    token_data = verify_token(data.refresh_token, expected_type="refresh")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    access_token = create_access_token(user.id, user.role.value)
    new_refresh_token = create_refresh_token(user.id, user.role.value)
    
    await log_action(
        db=db,
        action="TOKEN_REFRESHED",
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user (invalidate tokens on client side)."""
    await log_action(
        db=db,
        action="LOGOUT",
        resource_type="user",
        resource_id=current_user.id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change user password."""
    if not verify_password(data.current_password, current_user.hashed_password):
        await log_action(
            db=db,
            action="PASSWORD_CHANGE_FAILED",
            resource_type="user",
            resource_id=current_user.id,
            user_id=current_user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            details="Invalid current password",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    current_user.hashed_password = hash_password(data.new_password)
    
    await log_action(
        db=db,
        action="PASSWORD_CHANGED",
        resource_type="user",
        resource_id=current_user.id,
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user
