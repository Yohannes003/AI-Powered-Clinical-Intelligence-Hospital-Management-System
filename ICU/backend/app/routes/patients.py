"""
API routes for patient management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Patient, VitalSign, Alert
from app.schemas import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """Create a new ICU patient."""
    # Check if bed number is already occupied
    existing = db.query(Patient).filter(
        Patient.bed_number == patient.bed_number,
        Patient.is_active.is_(True)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Bed {patient.bed_number} is already occupied")

    db_patient = Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


@router.get("/", response_model=PatientListResponse)
def list_patients(
    status: Optional[str] = Query(None, regex="^(stable|critical|recovered)$"),
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List all patients with optional filtering."""
    query = db.query(Patient)

    if status:
        query = query.filter(Patient.status == status)
    if is_active is not None:
        query = query.filter(Patient.is_active == is_active)

    total = query.count()
    patients = query.order_by(desc(Patient.created_at)).offset(skip).limit(limit).all()

    # Enrich with counts
    result = []
    for p in patients:
        p_dict = {
            **p.__dict__,
            "vital_count": db.query(VitalSign).filter(VitalSign.patient_id == p.id).count(),
            "alert_count": db.query(Alert).filter(Alert.patient_id == p.id).count()
        }
        result.append(p_dict)

    return {"patients": result, "total": total}


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get a specific patient by ID."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient_dict = {
        **patient.__dict__,
        "vital_count": db.query(VitalSign).filter(VitalSign.patient_id == patient.id).count(),
        "alert_count": db.query(Alert).filter(Alert.patient_id == patient.id).count()
    }
    return patient_dict


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    update: PatientUpdate,
    db: Session = Depends(get_db)
):
    """Update patient information."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Soft-delete a patient (mark as inactive)."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.is_active = False
    patient.status = "recovered"
    db.commit()
    return {"message": f"Patient {patient_id} discharged", "patient_id": patient_id}


@router.get("/{patient_id}/stats")
def get_patient_stats(patient_id: int, db: Session = Depends(get_db)):
    """Get comprehensive statistics for a patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Latest vitals
    latest_vital = db.query(VitalSign).filter(
        VitalSign.patient_id == patient_id
    ).order_by(desc(VitalSign.timestamp)).first()

    # Alert counts by severity
    alert_counts = db.query(
        Alert.severity,
        func.count(Alert.id)
    ).filter(Alert.patient_id == patient_id).group_by(Alert.severity).all()

    # Risk trend (last 24 vitals)
    risk_trend = db.query(VitalSign).filter(
        VitalSign.patient_id == patient_id
    ).order_by(desc(VitalSign.timestamp)).limit(24).all()

    return {
        "patient_id": patient_id,
        "patient_name": patient.name,
        "current_risk_score": patient.risk_score,
        "current_status": patient.status,
        "latest_vitals": {
            "heart_rate": latest_vital.heart_rate if latest_vital else None,
            "blood_pressure_systolic": latest_vital.blood_pressure_systolic if latest_vital else None,
            "spo2": latest_vital.spo2 if latest_vital else None,
            "respiratory_rate": latest_vital.respiratory_rate if latest_vital else None,
            "timestamp": latest_vital.timestamp.isoformat() if latest_vital else None,
        },
        "alert_summary": {severity: count for severity, count in alert_counts},
        "risk_trend": [
            {"timestamp": v.timestamp.isoformat(), "score": v.risk_score, "level": v.risk_level}
            for v in reversed(risk_trend)
        ]
    }
