from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.referral_service import ReferralService
from app.services.ai_service import AIService
from app.services.patient_service import PatientService
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService

router = APIRouter(prefix="/referrals", tags=["Referrals"])

SPECIALTIES = [
    "Cardiology", "Neurology", "Pulmonology", "Nephrology",
    "Gastroenterology", "Oncology", "Endocrinology", "Rheumatology",
    "Infectious Disease", "Orthopedics", "Psychiatry", "Ophthalmology",
    "ENT", "Dermatology", "Urology", "Hematology", "General Surgery",
    "ICU / Critical Care", "Palliative Care", "Radiology",
]


class CreateReferralRequest(BaseModel):
    patient_id:           int
    specialty_requested:  str
    reason:               str
    priority:             str = "routine"      # routine | urgent | stat
    specialist_id:        Optional[int] = None
    clinical_summary:     Optional[str] = None
    notes_from_referring: Optional[str] = None
    diagnosis_ids:        Optional[List[int]] = []
    include_ai_snapshot:  bool = True


class AcceptReferralRequest(BaseModel):
    notes: Optional[str] = None


class DeclineReferralRequest(BaseModel):
    reason: str


class CompleteReferralRequest(BaseModel):
    follow_up_date: Optional[datetime] = None


class ConsultationNoteRequest(BaseModel):
    body:         str
    note_type:    str = "consultation"    # consultation | follow_up | discharge
    title:        Optional[str] = None
    findings:     Optional[str] = None
    plan:         Optional[str] = None
    medications:  Optional[List[str]] = []
    follow_up_in: Optional[str] = None


# ── Create Referral ───────────────────────────────────────

@router.post("/", status_code=201)
async def create_referral(
    body: CreateReferralRequest,
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_ADD)),
):
    if body.specialty_requested not in SPECIALTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid specialty. Choose from: {SPECIALTIES}"
        )

    # Optionally grab latest AI risk snapshot
    ai_snapshot = None
    if body.include_ai_snapshot:
        try:
            result  = await AIService.run_full_assessment(db, body.patient_id, current_user.id)
            ai_snapshot = {
                "risk_score":    result["risk_assessment"]["risk_score"],
                "risk_level":    result["risk_assessment"]["risk_level"],
                "confidence":    result["risk_assessment"]["confidence_score"],
                "explanation":   result["risk_assessment"]["explanation"][:3],
                "snapshot_time": datetime.utcnow().isoformat(),
            }
        except Exception:
            pass   # non-fatal

    referral = await ReferralService.create(
        db,
        referring_doctor_id  = current_user.id,
        patient_id           = body.patient_id,
        specialty_requested  = body.specialty_requested,
        reason               = body.reason,
        priority             = body.priority,
        specialist_id        = body.specialist_id,
        clinical_summary     = body.clinical_summary,
        notes_from_referring = body.notes_from_referring,
        diagnosis_ids        = body.diagnosis_ids,
        ai_risk_snapshot     = ai_snapshot,
    )

    await publish_event(
        EventType.DIAGNOSIS_ADDED,
        aggregate_type = "Referral",
        aggregate_id   = str(referral.id),
        payload        = {
            "referral_number":   referral.referral_number,
            "patient_id":        body.patient_id,
            "specialty":         body.specialty_requested,
            "priority":          body.priority,
            "referring_doctor":  current_user.full_name,
        }
    )
    await AuditService.log(
        db, action="referral.create",
        user_id=current_user.id,
        resource_type="referral", resource_id=str(referral.id),
        new_values={"specialty": body.specialty_requested, "patient_id": body.patient_id,
                    "priority": body.priority}
    )

    return {
        "message":        "Referral created",
        "referral_id":    referral.id,
        "referral_number":referral.referral_number,
        "status":         referral.status,
        "priority":       referral.priority,
        "ai_snapshot_included": ai_snapshot is not None,
    }


# ── List Referrals ────────────────────────────────────────

@router.get("/")
async def list_referrals(
    role:   str = Query("both", description="referring | specialist | both"),
    status: Optional[str] = None,
    skip:   int = Query(0, ge=0),
    limit:  int = Query(30, ge=1, le=100),
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_VIEW)),
):
    referrals = await ReferralService.list_for_doctor(
        db, current_user.id, role, status, skip, limit
    )
    return {"total": len(referrals), "referrals": referrals}


@router.get("/stats")
async def referral_stats(
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_VIEW)),
):
    return await ReferralService.get_stats(db, current_user.id)


@router.get("/specialties")
async def get_specialties():
    return {"specialties": SPECIALTIES}


# ── Accept / Decline / Complete ───────────────────────────

@router.post("/{referral_id}/accept")
async def accept_referral(
    referral_id: int,
    body: AcceptReferralRequest,
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_ADD)),
):
    ref = await ReferralService.accept(db, referral_id, current_user.id, body.notes)
    await AuditService.log(db, action="referral.accept", user_id=current_user.id,
                           resource_type="referral", resource_id=str(referral_id))
    return {"message": "Referral accepted", "referral_number": ref.referral_number,
            "accepted_at": ref.accepted_at.isoformat() if ref.accepted_at else None}


@router.post("/{referral_id}/decline")
async def decline_referral(
    referral_id: int,
    body: DeclineReferralRequest,
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_ADD)),
):
    ref = await ReferralService.decline(db, referral_id, current_user.id, body.reason)
    await AuditService.log(db, action="referral.decline", user_id=current_user.id,
                           resource_type="referral", resource_id=str(referral_id),
                           new_values={"reason": body.reason})
    return {"message": "Referral declined", "referral_number": ref.referral_number}


@router.post("/{referral_id}/complete")
async def complete_referral(
    referral_id: int,
    body: CompleteReferralRequest,
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_ADD)),
):
    ref = await ReferralService.complete(db, referral_id, current_user.id, body.follow_up_date)
    await AuditService.log(db, action="referral.complete", user_id=current_user.id,
                           resource_type="referral", resource_id=str(referral_id))
    return {"message": "Referral marked as complete", "completed_at": ref.completed_at.isoformat()}


# ── Consultation Notes ────────────────────────────────────

@router.post("/{referral_id}/notes", status_code=201)
async def add_consultation_note(
    referral_id: int,
    body: ConsultationNoteRequest,
    db: AsyncSession   = Depends(get_db),
    current_user       = Depends(require_permission(Permission.DIAGNOSIS_ADD)),
):
    note = await ReferralService.add_consultation_note(
        db,
        referral_id  = referral_id,
        author_id    = current_user.id,
        body         = body.body,
        note_type    = body.note_type,
        title        = body.title,
        findings     = body.findings,
        plan         = body.plan,
        medications  = body.medications,
        follow_up_in = body.follow_up_in,
    )
    await AuditService.log(db, action="referral.note.add", user_id=current_user.id,
                           resource_type="referral", resource_id=str(referral_id),
                           new_values={"note_type": body.note_type})
    return {
        "message":   "Consultation note added",
        "note_id":   note.id,
        "note_type": note.note_type,
        "title":     note.title,
    }
