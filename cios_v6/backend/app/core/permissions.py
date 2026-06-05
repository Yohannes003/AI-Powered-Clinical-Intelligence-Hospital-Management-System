"""
CIOS RBAC Permission System
Every permission is explicitly defined and checked via dependency injection.
"""
from enum import Enum
from typing import Set, Dict
from fastapi import Depends, HTTPException, status
from app.core.security import get_current_user


# ── All system permissions ────────────────────────────────
class Permission(str, Enum):
    # User management
    USER_APPROVE        = "user:approve"
    USER_REJECT         = "user:reject"
    USER_MANAGE         = "user:manage"
    USER_VIEW_ALL       = "user:view_all"

    # Patient management
    PATIENT_CREATE      = "patient:create"
    PATIENT_VIEW        = "patient:view"
    PATIENT_EDIT        = "patient:edit"
    PATIENT_DELETE      = "patient:delete"

    # Clinical
    VITALS_RECORD       = "vitals:record"
    VITALS_VIEW         = "vitals:view"
    DIAGNOSIS_ADD       = "diagnosis:add"
    DIAGNOSIS_VIEW      = "diagnosis:view"
    LAB_ORDER           = "lab:order"
    LAB_VIEW            = "lab:view"
    LAB_RESULT_ENTER    = "lab:result_enter"
    PRESCRIPTION_WRITE  = "prescription:write"

    # AI
    AI_ASSESS           = "ai:assess"
    AI_VIEW             = "ai:view"
    AI_REVIEW           = "ai:review"

    # Alerts
    ALERT_VIEW          = "alert:view"
    ALERT_ACKNOWLEDGE   = "alert:acknowledge"

    # Reports
    REPORT_GENERATE     = "report:generate"
    REPORT_DOWNLOAD     = "report:download"
    REPORT_VIEW         = "report:view"

    # Audit
    AUDIT_VIEW_OWN      = "audit:view_own"
    AUDIT_VIEW_ALL      = "audit:view_all"

    # Messaging
    MESSAGE_SEND        = "message:send"
    MESSAGE_VIEW        = "message:view"

    # Referrals
    REFERRAL_CREATE     = "referral:create"
    REFERRAL_VIEW       = "referral:view"
    REFERRAL_MANAGE     = "referral:manage"

    # Medication Orders & Drug Safety
    MEDICATION_ORDER_CREATE = "medication:order_create"
    MEDICATION_ORDER_VIEW   = "medication:order_view"
    MEDICATION_ADMINISTER   = "medication:administer"
    DRUG_SAFETY_CHECK       = "drug_safety:check"

    # Clinical Notes
    NOTE_CREATE             = "note:create"
    NOTE_VIEW              = "note:view"

    # System
    SYSTEM_SETTINGS     = "system:settings"
    SYSTEM_STATS        = "system:stats"


# ── Role → Permission mapping ─────────────────────────────
ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {

    "admin": {p for p in Permission},  # All permissions

    "doctor": {
        Permission.PATIENT_CREATE,
        Permission.PATIENT_VIEW,
        Permission.PATIENT_EDIT,
        Permission.VITALS_RECORD,
        Permission.VITALS_VIEW,
        Permission.DIAGNOSIS_ADD,
        Permission.DIAGNOSIS_VIEW,
        Permission.LAB_ORDER,
        Permission.LAB_VIEW,
        Permission.PRESCRIPTION_WRITE,
        Permission.AI_ASSESS,
        Permission.AI_VIEW,
        Permission.AI_REVIEW,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.REPORT_GENERATE,
        Permission.REPORT_DOWNLOAD,
        Permission.REPORT_VIEW,
        Permission.AUDIT_VIEW_OWN,
        Permission.SYSTEM_STATS,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.REFERRAL_CREATE,
        Permission.REFERRAL_VIEW,
        Permission.REFERRAL_MANAGE,
        Permission.MEDICATION_ORDER_CREATE,
        Permission.MEDICATION_ORDER_VIEW,
        Permission.MEDICATION_ADMINISTER,
        Permission.DRUG_SAFETY_CHECK,
        Permission.NOTE_CREATE,
        Permission.NOTE_VIEW,
    },

    "nurse": {
        Permission.PATIENT_VIEW,
        Permission.VITALS_RECORD,
        Permission.VITALS_VIEW,
        Permission.DIAGNOSIS_VIEW,
        Permission.LAB_VIEW,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.AUDIT_VIEW_OWN,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.REFERRAL_VIEW,
        Permission.MEDICATION_ORDER_VIEW,
        Permission.MEDICATION_ADMINISTER,
        Permission.NOTE_CREATE,
        Permission.NOTE_VIEW,
    },

    "lab_tech": {
        Permission.PATIENT_VIEW,
        Permission.LAB_VIEW,
        Permission.LAB_RESULT_ENTER,
        Permission.ALERT_VIEW,
        Permission.AUDIT_VIEW_OWN,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
    },

    "viewer": {
        Permission.PATIENT_VIEW,
        Permission.VITALS_VIEW,
        Permission.DIAGNOSIS_VIEW,
        Permission.LAB_VIEW,
        Permission.AUDIT_VIEW_OWN,
    },
}


def get_user_permissions(role: str) -> Set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: Permission) -> bool:
    return permission in get_user_permissions(role)


# ── FastAPI dependency factories ─────────────────────────

def require_permission(permission: Permission):
    """Dependency: requires a specific permission."""
    async def checker(current_user=Depends(get_current_user)):
        if not current_user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required. Your role ({current_user.role}) does not have this access."
            )
        return current_user
    return checker


def require_any_permission(*permissions: Permission):
    """Dependency: requires ANY one of the given permissions."""
    async def checker(current_user=Depends(get_current_user)):
        if not current_user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
        user_perms = get_user_permissions(current_user.role)
        if not any(p in user_perms for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required one of: {[p.value for p in permissions]}"
            )
        return current_user
    return checker


def require_admin():
    return require_permission(Permission.USER_MANAGE)
