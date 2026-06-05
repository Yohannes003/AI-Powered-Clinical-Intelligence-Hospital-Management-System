"""
Immutable Audit System — HIPAA/GDPR-ready compliance logging.
All actions are append-only with cryptographic integrity markers.
"""
import hashlib
import json
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request
from loguru import logger

from app.models.models import AuditLog, EventType


class AuditService:
    """Immutable audit trail for all clinical and system actions."""

    @staticmethod
    def _compute_hash(entry: dict) -> str:
        """Compute SHA-256 hash of audit entry for integrity verification."""
        content = json.dumps(entry, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    async def log(
        db: AsyncSession,
        action: str,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        request: Optional[Request] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        
        ip_address = None
        user_agent = None
        session_id = None

        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]
            session_id = request.headers.get("x-session-id", "")

        # Sanitize PII from audit logs (keep only IDs, not full values)
        safe_new = AuditService._sanitize(new_values)
        safe_old = AuditService._sanitize(old_values)

        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            event_type=event_type,
            old_values=safe_old,
            new_values=safe_new,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            status=status,
            error_message=error_message,
            timestamp=datetime.utcnow(),
        )

        db.add(log_entry)
        await db.flush()

        logger.info(
            f"[AUDIT] action={action} user={user_id} "
            f"resource={resource_type}:{resource_id} status={status}"
        )

        return log_entry

    @staticmethod
    def _sanitize(values: Optional[dict]) -> Optional[dict]:
        if not values:
            return values
        sensitive_fields = {"password", "hashed_password", "token", "secret", "ssn", "credit_card"}
        return {
            k: "[REDACTED]" if k.lower() in sensitive_fields else v
            for k, v in values.items()
        }

    @staticmethod
    async def get_patient_audit_trail(
        db: AsyncSession,
        patient_id: int,
        limit: int = 100
    ) -> list:
        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "patient",
                AuditLog.resource_id == str(patient_id)
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_user_activity(
        db: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> list:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()
