from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.models import Diagnosis, LabResult, Visit, ClinicalAlert
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService

router = APIRouter(prefix="/clinical", tags=["Clinical"])


class DiagnosisCreate(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    icd_code: Optional[str] = None
    condition_name: str
    severity: Optional[str] = "moderate"
    description: Optional[str] = None
    treatment_plan: Optional[str] = None
    medications_prescribed: Optional[List[str]] = []
    is_primary: bool = False


class LabResultCreate(BaseModel):
    patient_id: int
    test_name: str
    test_code: Optional[str] = None
    category: Optional[str] = None
    results: Optional[dict] = None
    raw_value: Optional[str] = None
    is_critical: bool = False
    notes: Optional[str] = None


class VisitCreate(BaseModel):
    patient_id: int
    visit_type: Optional[str] = "routine"
    chief_complaint: Optional[str] = None
    symptoms: Optional[List[str]] = []
    notes: Optional[str] = None


@router.post("/diagnoses", status_code=201)
async def add_diagnosis(
    body: DiagnosisCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    diagnosis = Diagnosis(
        doctor_id=current_user.id,
        **body.dict()
    )
    db.add(diagnosis)
    await db.flush()

    await publish_event(
        EventType.DIAGNOSIS_ADDED,
        aggregate_type="Patient",
        aggregate_id=str(body.patient_id),
        payload={
            "diagnosis_id": diagnosis.id,
            "condition": body.condition_name,
            "severity": body.severity,
            "patient_id": body.patient_id
        }
    )

    await AuditService.log(
        db, action="diagnosis.add",
        user_id=current_user.id,
        resource_type="patient",
        resource_id=str(body.patient_id),
        event_type=EventType.DIAGNOSIS_ADDED,
        new_values={"condition": body.condition_name, "severity": body.severity}
    )

    return {
        "message": "Diagnosis added",
        "diagnosis_id": diagnosis.id,
        "condition": body.condition_name,
    }


@router.get("/diagnoses/{patient_id}")
async def get_diagnoses(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if patient_id.startswith('icu-'):
        return {"patient_id": patient_id, "diagnoses": []}
    pid = int(patient_id)
    result = await db.execute(
        select(Diagnosis)
        .where(Diagnosis.patient_id == pid)
        .order_by(Diagnosis.diagnosed_at.desc())
    )
    diagnoses = result.scalars().all()
    return {
        "patient_id": patient_id,
        "diagnoses": [
            {c.name: getattr(d, c.name) for c in d.__table__.columns}
            for d in diagnoses
        ]
    }


@router.post("/labs", status_code=201)
async def add_lab_result(
    body: LabResultCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    lab = LabResult(
        ordered_by_id=current_user.id,
        resulted_at=datetime.utcnow(),
        status="resulted",
        **body.dict()
    )
    db.add(lab)
    await db.flush()

    await publish_event(
        EventType.LAB_RESULT_UPDATED,
        aggregate_type="Patient",
        aggregate_id=str(body.patient_id),
        payload={
            "lab_id": lab.id,
            "test_name": body.test_name,
            "is_critical": body.is_critical,
        }
    )

    return {"message": "Lab result recorded", "lab_id": lab.id}


@router.get("/labs/{patient_id}")
async def get_labs(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if patient_id.startswith('icu-'):
        return {"patient_id": patient_id, "labs": []}
    pid = int(patient_id)
    result = await db.execute(
        select(LabResult)
        .where(LabResult.patient_id == pid)
        .order_by(LabResult.resulted_at.desc())
    )
    labs = result.scalars().all()
    return {
        "patient_id": patient_id,
        "labs": [
            {c.name: getattr(l, c.name) for c in l.__table__.columns}
            for l in labs
        ]
    }


@router.post("/visits", status_code=201)
async def create_visit(
    body: VisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    visit = Visit(doctor_id=current_user.id, **body.dict())
    db.add(visit)
    await db.flush()
    return {"message": "Visit created", "visit_id": visit.id}


@router.get("/alerts/{patient_id}")
async def get_patient_alerts(
    patient_id: str,
    unacknowledged_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if patient_id.startswith('icu-'):
        return {"patient_id": patient_id, "alerts": []}
    pid = int(patient_id)
    query = select(ClinicalAlert).where(ClinicalAlert.patient_id == pid)
    if unacknowledged_only:
        query = query.where(ClinicalAlert.is_acknowledged == False)
    result = await db.execute(query.order_by(ClinicalAlert.created_at.desc()).limit(50))
    alerts = result.scalars().all()
    return {
        "patient_id": patient_id,
        "alerts": [
            {c.name: getattr(a, c.name) for c in a.__table__.columns}
            for a in alerts
        ]
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(ClinicalAlert).where(ClinicalAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_by_id = current_user.id
    alert.acknowledged_at = datetime.utcnow()
    await db.flush()
    return {"message": "Alert acknowledged", "alert_id": alert_id}
