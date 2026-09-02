from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog
from typing import Optional


async def log_action(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
):
    """Log an action for audit purposes."""
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(audit_log)
    await db.flush()
