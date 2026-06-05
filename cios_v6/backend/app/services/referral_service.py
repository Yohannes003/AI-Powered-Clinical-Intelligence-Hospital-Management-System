"""
Referral Service — clinical referral workflow.
Handles creation, acceptance, decline, consultation notes, and AI snapshot.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.models import (
    Referral, ConsultationNote, ReferralStatus,
    ReferralPriority, Patient, User
)


def _gen_referral_number() -> str:
    ts  = datetime.utcnow().strftime("%Y%m%d")
    uid = str(uuid.uuid4().int)[:5]
    return f"REF-{ts}-{uid}"


def _serialize_referral(r: Referral) -> dict:
    return {
        "id":                    r.id,
        "referral_number":       r.referral_number,
        "patient_id":            r.patient_id,
        "referring_doctor_id":   r.referring_doctor_id,
        "specialist_id":         r.specialist_id,
        "specialty_requested":   r.specialty_requested,
        "reason":                r.reason,
        "clinical_summary":      r.clinical_summary,
        "priority":              r.priority,
        "status":                r.status,
        "ai_risk_snapshot":      r.ai_risk_snapshot,
        "notes_from_referring":  r.notes_from_referring,
        "notes_from_specialist": r.notes_from_specialist,
        "accepted_at":           r.accepted_at.isoformat()  if r.accepted_at  else None,
        "completed_at":          r.completed_at.isoformat() if r.completed_at else None,
        "follow_up_date":        r.follow_up_date.isoformat() if r.follow_up_date else None,
        "created_at":            r.created_at.isoformat()   if r.created_at   else None,
        "consultation_notes":    [],   # filled below when needed
        # joined fields (set externally)
        "patient_name":          None,
        "referring_doctor_name": None,
        "specialist_name":       None,
    }


class ReferralService:

    # ── Create ────────────────────────────────────────────

    @staticmethod
    async def create(
        db: AsyncSession,
        referring_doctor_id: int,
        patient_id: int,
        specialty_requested: str,
        reason: str,
        priority: str = "routine",
        specialist_id: Optional[int] = None,
        clinical_summary: Optional[str] = None,
        notes_from_referring: Optional[str] = None,
        diagnosis_ids: Optional[List[int]] = None,
        ai_risk_snapshot: Optional[dict] = None,
    ) -> Referral:

        referral = Referral(
            referral_number      = _gen_referral_number(),
            patient_id           = patient_id,
            referring_doctor_id  = referring_doctor_id,
            specialist_id        = specialist_id,
            specialty_requested  = specialty_requested,
            reason               = reason,
            clinical_summary     = clinical_summary,
            priority             = ReferralPriority(priority) if priority in ("routine","urgent","stat") else ReferralPriority.ROUTINE,
            status               = ReferralStatus.PENDING,
            notes_from_referring = notes_from_referring,
            diagnosis_ids        = diagnosis_ids or [],
            ai_risk_snapshot     = ai_risk_snapshot,
        )
        db.add(referral)
        await db.flush()
        return referral

    # ── Accept / Decline ──────────────────────────────────

    @staticmethod
    async def accept(
        db: AsyncSession,
        referral_id: int,
        specialist_id: int,
        notes: Optional[str] = None,
    ) -> Referral:
        ref = await ReferralService._get_or_404(db, referral_id)
        if ref.status != ReferralStatus.PENDING:
            raise ValueError(f"Cannot accept a referral with status '{ref.status}'")
        ref.status       = ReferralStatus.ACCEPTED
        ref.specialist_id= specialist_id
        ref.accepted_at  = datetime.utcnow()
        if notes:
            ref.notes_from_specialist = notes
        await db.flush()
        return ref

    @staticmethod
    async def decline(
        db: AsyncSession,
        referral_id: int,
        specialist_id: int,
        reason: str,
    ) -> Referral:
        ref = await ReferralService._get_or_404(db, referral_id)
        ref.status                = ReferralStatus.DECLINED
        ref.notes_from_specialist = reason
        await db.flush()
        return ref

    @staticmethod
    async def complete(
        db: AsyncSession,
        referral_id: int,
        specialist_id: int,
        follow_up_date: Optional[datetime] = None,
    ) -> Referral:
        ref = await ReferralService._get_or_404(db, referral_id)
        ref.status        = ReferralStatus.COMPLETED
        ref.completed_at  = datetime.utcnow()
        ref.follow_up_date= follow_up_date
        await db.flush()
        return ref

    # ── Consultation Notes ────────────────────────────────

    @staticmethod
    async def add_consultation_note(
        db: AsyncSession,
        referral_id: int,
        author_id: int,
        body: str,
        note_type: str = "consultation",
        title: Optional[str] = None,
        findings: Optional[str] = None,
        plan: Optional[str] = None,
        medications: Optional[List[str]] = None,
        follow_up_in: Optional[str] = None,
    ) -> ConsultationNote:
        note = ConsultationNote(
            referral_id  = referral_id,
            author_id    = author_id,
            note_type    = note_type,
            title        = title or f"{note_type.replace('_',' ').title()} Note",
            body         = body,
            findings     = findings,
            plan         = plan,
            medications  = medications or [],
            follow_up_in = follow_up_in,
        )
        db.add(note)
        await db.flush()
        return note

    # ── Queries ───────────────────────────────────────────

    @staticmethod
    async def list_for_doctor(
        db: AsyncSession,
        doctor_id: int,
        role: str = "referring",    # referring | specialist | both
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 30,
    ) -> List[dict]:
        if role == "referring":
            cond = Referral.referring_doctor_id == doctor_id
        elif role == "specialist":
            cond = Referral.specialist_id == doctor_id
        else:
            cond = (
                (Referral.referring_doctor_id == doctor_id) |
                (Referral.specialist_id == doctor_id)
            )

        q = select(Referral).where(cond)
        if status:
            q = q.where(Referral.status == status)
        q = q.order_by(
            # STAT first, then urgent, then routine; newest first within group
            desc(Referral.priority == "stat"),
            desc(Referral.priority == "urgent"),
            desc(Referral.created_at),
        ).offset(skip).limit(limit)

        rows = (await db.execute(q)).scalars().all()

        # Hydrate patient + doctor names
        result = []
        for ref in rows:
            d = _serialize_referral(ref)

            # patient name
            if ref.patient_id:
                p = (await db.execute(
                    select(Patient).where(Patient.id == ref.patient_id)
                )).scalar_one_or_none()
                if p: d["patient_name"] = p.full_name

            # referring doctor name
            rd = (await db.execute(
                select(User).where(User.id == ref.referring_doctor_id)
            )).scalar_one_or_none()
            if rd: d["referring_doctor_name"] = rd.full_name

            # specialist name
            if ref.specialist_id:
                sp = (await db.execute(
                    select(User).where(User.id == ref.specialist_id)
                )).scalar_one_or_none()
                if sp: d["specialist_name"] = sp.full_name

            # consultation notes
            notes_q = (
                select(ConsultationNote, User)
                .join(User, ConsultationNote.author_id == User.id)
                .where(ConsultationNote.referral_id == ref.id)
                .order_by(ConsultationNote.created_at)
            )
            notes_rows = (await db.execute(notes_q)).all()
            d["consultation_notes"] = [
                {
                    "id":          n.ConsultationNote.id,
                    "note_type":   n.ConsultationNote.note_type,
                    "title":       n.ConsultationNote.title,
                    "body":        n.ConsultationNote.body,
                    "findings":    n.ConsultationNote.findings,
                    "plan":        n.ConsultationNote.plan,
                    "medications": n.ConsultationNote.medications,
                    "follow_up_in":n.ConsultationNote.follow_up_in,
                    "author_name": n.User.full_name,
                    "author_role": n.User.role,
                    "created_at":  n.ConsultationNote.created_at.isoformat()
                                   if n.ConsultationNote.created_at else None,
                }
                for n in notes_rows
            ]
            result.append(d)
        return result

    @staticmethod
    async def get_stats(db: AsyncSession, doctor_id: int) -> dict:
        base = select(func.count(Referral.id))
        sent_total    = (await db.execute(base.where(Referral.referring_doctor_id == doctor_id))).scalar()
        recv_total    = (await db.execute(base.where(Referral.specialist_id == doctor_id))).scalar()
        pending_recv  = (await db.execute(base.where(
            Referral.specialist_id == doctor_id, Referral.status == "pending"
        ))).scalar()
        stat_pending  = (await db.execute(base.where(
            Referral.referring_doctor_id == doctor_id, Referral.status == "pending",
            Referral.priority == "stat"
        ))).scalar()
        return {
            "sent_total":   sent_total   or 0,
            "recv_total":   recv_total   or 0,
            "pending_recv": pending_recv or 0,
            "stat_pending": stat_pending or 0,
        }

    @staticmethod
    async def _get_or_404(db: AsyncSession, referral_id: int) -> Referral:
        ref = (await db.execute(
            select(Referral).where(Referral.id == referral_id)
        )).scalar_one_or_none()
        if not ref:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Referral {referral_id} not found")
        return ref
