from datetime import datetime, timedelta, UTC
from typing import Optional

import jwt
from pydantic import BaseModel

from app.config import get_settings

ALGORITHM = "HS256"  # fixed in code, not configurable
REQUIRED_CLAIMS = ("exp", "iat", "sub", "type", "role")


class TokenData(BaseModel):
    user_id: str
    role: str
    token_type: str  # "access" or "refresh"
    exp: datetime


def _create_token(user_id: str, role: str, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    minutes = get_settings().access_token_expire_minutes
    return _create_token(user_id, role, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: str, role: str) -> str:
    days = get_settings().refresh_token_expire_days
    return _create_token(user_id, role, "refresh", timedelta(days=days))


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenData]:
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],
            options={"require": list(REQUIRED_CLAIMS)},  # fresh dict per call
        )
    except jwt.InvalidTokenError:  # base class: expired, bad sig, bad alg, missing claim
        return None

    if payload["type"] != expected_type:
        return None

    return TokenData(
        user_id=payload["sub"],
        role=payload["role"],
        token_type=payload["type"],
        exp=datetime.fromtimestamp(payload["exp"], UTC),
    )