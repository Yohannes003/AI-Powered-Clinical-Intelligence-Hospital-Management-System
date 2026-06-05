from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.db.session import get_db
from app.services.user_service import UserService
from app.core.security import create_access_token, create_refresh_token, get_current_user
from app.core.permissions import get_user_permissions
from app.audit.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication"])

VALID_ROLES = ["doctor", "nurse", "lab_tech", "viewer"]  # admin created manually only


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "doctor"
    department: Optional[str] = None
    license_number: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    permissions: list


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = await UserService.authenticate(db, req.email, req.password)
    if not user:
        await AuditService.log(
            db, action="auth.login.failed",
            resource_type="user", resource_id=req.email,
            request=request, status="failed",
            error_message="Invalid credentials"
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check approval status
    approval = getattr(user, 'approval_status', 'approved')
    if approval == 'pending':
        raise HTTPException(
            status_code=403,
            detail="Your account is pending admin approval. Please wait for approval before logging in."
        )
    if approval == 'rejected':
        reason = getattr(user, 'rejection_reason', 'No reason provided')
        raise HTTPException(
            status_code=403,
            detail=f"Your account has been rejected. Reason: {reason}"
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Contact admin.")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    permissions = [p.value for p in get_user_permissions(user.role)]

    await AuditService.log(
        db, action="auth.login.success",
        user_id=user.id,
        resource_type="user", resource_id=str(user.id),
        request=request
    )

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "department": getattr(user, 'department', None),
            "approval_status": approval,
        },
        permissions=permissions
    )


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validate role — users cannot self-register as admin
    if req.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{req.role}'. Must be one of: {VALID_ROLES}"
        )

    existing = await UserService.get_by_email(db, req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user with pending approval status
    user = await UserService.create(db, {
        **req.dict(),
        "approval_status": "pending",
        "is_active": False,   # inactive until admin approves
    })

    return {
        "message": "Registration submitted successfully. Your account is pending admin approval.",
        "status": "pending",
        "user_id": user.id,
        "email": user.email,
        "role_requested": user.role,
    }


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    permissions = [p.value for p in get_user_permissions(current_user.role)]
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": getattr(current_user, 'department', None),
        "license_number": getattr(current_user, 'license_number', None),
        "is_active": current_user.is_active,
        "approval_status": getattr(current_user, 'approval_status', 'approved'),
        "permissions": permissions,
        "permissions_count": len(permissions),
    }
