from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
from app.models.models import User
from app.core.security import hash_password, verify_password


class UserService:

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: dict) -> User:
        approval_status = data.get("approval_status", "approved")
        is_active       = data.get("is_active", approval_status == "approved")

        user = User(
            email           = data["email"],
            full_name       = data["full_name"],
            hashed_password = hash_password(data["password"]),
            role            = data.get("role", "doctor"),
            department      = data.get("department"),
            license_number  = data.get("license_number"),
            is_active       = is_active,
        )
        # Set approval fields if column exists
        if hasattr(user, 'approval_status'):
            user.approval_status = approval_status
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> Optional[User]:
        user = await UserService.get_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def list_users(db: AsyncSession, skip: int = 0, limit: int = 50):
        result = await db.execute(
            select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def seed_default_users(db: AsyncSession):
        """Seed default admin and doctor — auto-approved."""
        defaults = [
            {
                "email": "admin@cios.hospital",
                "full_name": "System Administrator",
                "password": "Admin@123",
                "role": "admin",
                "department": "Administration",
                "approval_status": "approved",
                "is_active": True,
            },
            {
                "email": "doctor@cios.hospital",
                "full_name": "Dr. Sarah Mitchell",
                "password": "Doctor@123",
                "role": "doctor",
                "department": "Internal Medicine",
                "license_number": "MD-2024-001",
                "approval_status": "approved",
                "is_active": True,
            },
            {
                "email": "nurse@cios.hospital",
                "full_name": "Nurse Aisha Khan",
                "password": "Nurse@123",
                "role": "nurse",
                "department": "ICU",
                "approval_status": "approved",
                "is_active": True,
            },
        ]
        for ud in defaults:
            existing = await UserService.get_by_email(db, ud["email"])
            if not existing:
                await UserService.create(db, ud)
