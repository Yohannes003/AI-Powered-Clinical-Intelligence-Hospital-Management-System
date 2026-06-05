from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.permissions import require_permission, Permission
from app.models.models import Patient, MedicationOrder, MedicationAdministration
from app.services.drug_safety import full_drug_safety_check, DRUG_CLASSES
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService

router = APIRouter(prefix="/orders", tags=["Medication Orders"])


class OrderRoute(str, Enum):
    ORAL = "oral"; IV = "iv"; IM = "im"; SUBQ = "subcutaneous"
    TOPICAL = "topical"; INHALED = "inhaled"; RECTAL = "rectal"; SL = "sublingual"


class OrderFrequency(str, Enum):
    ONCE = "once"; BID = "bid"; TID = "tid"; QID = "qid"
    Q4H = "q4h"; Q6H = "q6h"; Q8H = "q8h"; Q12H = "q12h"; Q24H = "q24h"
    PRN = "prn"; CONTINUOUS = "continuous"


class MedicationOrderCreate(BaseModel):
    patient_id: int
    medication_name: str
    dose: str
    dose_unit: str = "mg"
    route: OrderRoute = OrderRoute.ORAL
    frequency: OrderFrequency
    indication: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] = None
    is_stat: bool = False


class MAREntryCreate(BaseModel):
    order_id: int
    administered_at: datetime
    dose_given: str
    route: OrderRoute
    site: Optional[str] = None
    notes: Optional[str] = None
    witnessed_by: Optional[str] = None


def _get_drug_class(drug: str) -> str:
    d = drug.strip().lower()
    for cls_name, members in DRUG_CLASSES.items():
        if d in members:
            return cls_name
    return "unknown"


@router.post("/", status_code=201)
async def create_medication_order(
    body: MedicationOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PRESCRIPTION_WRITE)),
):
    result = await db.execute(select(Patient).where(Patient.id == body.patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing_meds = patient.current_medications or []
    allergies = patient.allergies or []
    safety = full_drug_safety_check(body.medication_name, existing_meds, allergies)

    safety_issues = []
    for i in safety.interactions:
        if i.severity in ("contraindicated", "major"):
            safety_issues.append(f"{i.severity.upper()}: {i.description}")
    for a in safety.allergies:
        if a.severity in ("high", "moderate"):
            safety_issues.append(f"ALLERGY: {a.description}")

    if safety_issues and not body.is_stat:
        return {
            "requires_override": True,
            "safety_issues": safety_issues,
            "message": "DRAFT pending safety review. Use is_stat=true to bypass.",
        }

    order = MedicationOrder(
        patient_id=body.patient_id,
        medication_name=body.medication_name,
        dose=body.dose,
        dose_unit=body.dose_unit,
        route=body.route.value,
        frequency=body.frequency.value,
        status="active" if body.is_stat or not safety_issues else "draft",
        ordered_by_id=current_user.id,
        indication=body.indication,
        notes=body.notes,
        is_stat=body.is_stat,
        start_date=body.start_date or datetime.utcnow(),
        end_date=body.end_date,
        safety_check_passed=len(safety_issues) == 0,
        safety_check_notes="; ".join(safety_issues) if safety_issues else None,
    )
    db.add(order)
    await db.flush()

    await publish_event(
        EventType.TREATMENT_STARTED,
        aggregate_type="Patient",
        aggregate_id=str(body.patient_id),
        payload={"order_id": order.id, "medication": body.medication_name, "ordered_by": current_user.id}
    )
    await AuditService.log(
        db, action="medication.order.create", user_id=current_user.id,
        resource_type="patient", resource_id=str(body.patient_id),
        event_type=EventType.TREATMENT_STARTED,
        new_values={"medication": body.medication_name, "dose": body.dose, "status": order.status}
    )

    return {
        "order_id": order.id,
        "status": order.status,
        "drug_class": _get_drug_class(body.medication_name),
        "safety_issues": safety_issues if safety_issues else None,
    }


@router.get("/patient/{patient_id}")
async def list_orders(
    patient_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PATIENT_VIEW)),
):
    query = select(MedicationOrder).where(MedicationOrder.patient_id == patient_id)
    if status:
        query = query.where(MedicationOrder.status == status)
    query = query.order_by(MedicationOrder.created_at.desc())
    result = await db.execute(query)
    orders = result.scalars().all()

    result_list = []
    for o in orders:
        mar_result = await db.execute(
            select(MedicationAdministration)
            .where(MedicationAdministration.order_id == o.id)
            .order_by(MedicationAdministration.administered_at.desc())
        )
        admins = mar_result.scalars().all()
        result_list.append({
            "id": o.id, "patient_id": o.patient_id,
            "medication_name": o.medication_name, "dose": o.dose,
            "dose_unit": o.dose_unit, "route": o.route, "frequency": o.frequency,
            "status": o.status, "ordered_by_id": o.ordered_by_id,
            "indication": o.indication, "notes": o.notes,
            "is_stat": o.is_stat, "start_date": o.start_date,
            "end_date": o.end_date,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "administrations": [
                {"id": a.id, "dose_given": a.dose_given, "route": a.route,
                 "administered_at": a.administered_at.isoformat() if a.administered_at else None,
                 "notes": a.notes}
                for a in admins
            ],
        })

    return {"patient_id": patient_id, "orders": result_list, "total": len(result_list)}


@router.post("/{order_id}/administer", status_code=201)
async def record_administration(
    order_id: int,
    body: MAREntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.VITALS_RECORD)),
):
    result = await db.execute(select(MedicationOrder).where(MedicationOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    mar = MedicationAdministration(
        order_id=order_id,
        administered_by_id=current_user.id,
        administered_at=body.administered_at,
        dose_given=body.dose_given,
        route=body.route.value,
        site=body.site,
        notes=body.notes,
        witnessed_by=body.witnessed_by,
    )
    db.add(mar)
    await db.flush()

    return {"administration_id": mar.id, "message": "Administration recorded"}
