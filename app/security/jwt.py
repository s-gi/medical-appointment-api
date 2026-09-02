from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from pydantic import BaseModel
from app.config import get_settings


class TokenData(BaseModel):
    user_id: str
    role: str
    token_type: str  # "access" or "refresh"
    exp: datetime


def create_access_token(user_id: str, role: str) -> str:
    """Create a new access token."""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: str, role: str) -> str:
    """Create a new refresh token."""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    
    payload = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenData]:
    """Verify and decode a token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        if payload.get("type") != expected_type:
            return None
        
        return TokenData(
            user_id=payload["sub"],
            role=payload["role"],
            token_type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"]),
        )
    except JWTError:
        return None
