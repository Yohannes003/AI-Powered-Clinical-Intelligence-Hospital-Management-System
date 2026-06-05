"""
Admin RBAC endpoints:
- Approval desk (pending signups)
- User management (role changes, activate/deactivate)
- Permission overview
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.core.permissions import require_permission, Permission, get_user_permissions
from app.models.models import User
from app.audit.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["Admin — RBAC"])


# ── Schemas ───────────────────────────────────────────────

class ApproveRequest(BaseModel):
    user_id: int
    role: Optional[str] = None        # optionally change role on approval
    department: Optional[str] = None

class RejectRequest(BaseModel):
    user_id: int
    reason: str

class UpdateRoleRequest(BaseModel):
    user_id: int
    role: str
    department: Optional[str] = None


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "department": getattr(u, 'department', None),
        "license_number": getattr(u, 'license_number', None),
        "is_active": u.is_active,
        "approval_status": getattr(u, 'approval_status', 'approved'),
        "approved_at": getattr(u, 'approved_at', None),
        "rejection_reason": getattr(u, 'rejection_reason', None),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ── Approval Desk ─────────────────────────────────────────

@router.get("/pending-approvals")
async def get_pending_approvals(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_APPROVE))
):
    """List all users awaiting admin approval."""
    result = await db.execute(
        select(User)
        .where(User.approval_status == "pending")
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return {
        "count": len(users),
        "pending": [serialize_user(u) for u in users]
    }


@router.post("/approve")
async def approve_user(
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_APPROVE))
):
    """Approve a pending user signup. Optionally assign/change role."""
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user, 'approval_status', 'approved') == 'approved':
        raise HTTPException(status_code=400, detail="User is already approved")

    user.approval_status  = "approved"
    user.is_active        = True
    user.approved_by_id   = admin.id
    user.approved_at      = datetime.utcnow()
    user.rejection_reason = None

    if body.role:
        valid_roles = ["admin", "doctor", "nurse", "lab_tech", "viewer"]
        if body.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
        user.role = body.role

    if body.department:
        user.department = body.department

    await db.flush()

    await AuditService.log(
        db, action="admin.user.approve",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        new_values={"approved_user": user.email, "role": user.role, "approved_by": admin.email}
    )

    return {
        "message": f"✅ {user.full_name} approved as {user.role}",
        "user": serialize_user(user)
    }


@router.post("/reject")
async def reject_user(
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_REJECT))
):
    """Reject a pending user signup with a reason."""
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.approval_status  = "rejected"
    user.is_active        = False
    user.rejection_reason = body.reason
    await db.flush()

    await AuditService.log(
        db, action="admin.user.reject",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        new_values={"rejected_user": user.email, "reason": body.reason}
    )

    return {"message": f"❌ {user.full_name} rejected", "reason": body.reason}


# ── User Management ───────────────────────────────────────

@router.get("/users")
async def list_all_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_VIEW_ALL))
):
    """List all users in the system with optional filters."""
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if status == "active":
        query = query.where(User.is_active == True)
    elif status == "inactive":
        query = query.where(User.is_active == False)
    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {
        "total": len(users),
        "users": [serialize_user(u) for u in users]
    }


@router.patch("/users/role")
async def update_user_role(
    body: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_MANAGE))
):
    """Change a user's role. Only admin can do this."""
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    valid_roles = ["admin", "doctor", "nurse", "lab_tech", "viewer"]
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

    if user.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot change your own admin role")

    old_role   = user.role
    user.role  = body.role
    if body.department:
        user.department = body.department
    await db.flush()

    await AuditService.log(
        db, action="admin.user.role_change",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user.id),
        old_values={"role": old_role},
        new_values={"role": body.role, "department": body.department}
    )

    return {
        "message": f"Role updated: {user.full_name} is now {body.role}",
        "user": serialize_user(user)
    }


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_MANAGE))
):
    """Enable or disable a user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user.is_active = not user.is_active
    await db.flush()

    action = "activated" if user.is_active else "deactivated"
    await AuditService.log(
        db, action=f"admin.user.{action}",
        user_id=admin.id,
        resource_type="user",
        resource_id=str(user_id),
        new_values={"is_active": user.is_active, "target_user": user.email}
    )

    return {
        "message": f"User {user.full_name} {action}",
        "is_active": user.is_active
    }


# ── Permissions Overview ──────────────────────────────────

@router.get("/permissions")
async def get_permissions_matrix(
    admin=Depends(require_permission(Permission.USER_VIEW_ALL))
):
    """Return full permission matrix for all roles."""
    roles = ["admin", "doctor", "nurse", "lab_tech", "viewer"]
    matrix = {}
    for role in roles:
        perms = get_user_permissions(role)
        matrix[role] = [p.value for p in sorted(perms, key=lambda x: x.value)]
    return {"roles": roles, "permissions": matrix}


@router.get("/my-permissions")
async def get_my_permissions(
    current_user=Depends(require_permission(Permission.AUDIT_VIEW_OWN))
):
    """Return the calling user's own permissions."""
    perms = get_user_permissions(current_user.role)
    return {
        "user": current_user.full_name,
        "role": current_user.role,
        "permissions": sorted([p.value for p in perms]),
        "total": len(perms)
    }


# ── System Stats ─────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_permission(Permission.USER_VIEW_ALL))
):
    """Dashboard stats for admin panel."""
    roles = ["admin", "doctor", "nurse", "lab_tech", "viewer"]
    stats = {"by_role": {}, "pending_approvals": 0, "total_users": 0, "active_users": 0}

    for role in roles:
        r = await db.execute(select(func.count(User.id)).where(User.role == role))
        stats["by_role"][role] = r.scalar()

    total  = await db.execute(select(func.count(User.id)))
    active = await db.execute(select(func.count(User.id)).where(User.is_active == True))
    pending = await db.execute(
        select(func.count(User.id)).where(User.approval_status == "pending")
    )

    stats["total_users"]       = total.scalar()
    stats["active_users"]      = active.scalar()
    stats["pending_approvals"] = pending.scalar()
    return stats
