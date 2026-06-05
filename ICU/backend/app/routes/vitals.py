"""
API routes for vital signs and dashboard data.
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Patient, VitalSign, Alert
from app.schemas import (
    VitalSignCreate, VitalSignResponse, VitalSignHistory,
    RealTimeVital, DashboardStats, RiskDistribution, AlertStats
)
from app.websocket_manager import manager
from app.risk_engine import risk_engine

router = APIRouter(tags=["vitals"])


@router.get("/vitals/{patient_id}", response_model=VitalSignHistory)
def get_patient_vitals(
    patient_id: int,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db)
):
    """Get vital signs history for a patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    since = datetime.now() - timedelta(hours=hours)
    vitals = db.query(VitalSign).filter(
        VitalSign.patient_id == patient_id,
        VitalSign.timestamp >= since
    ).order_by(desc(VitalSign.timestamp)).limit(limit).all()

    return {
        "patient_id": patient_id,
        "vitals": vitals,
        "total": len(vitals)
    }


@router.get("/vitals/{patient_id}/latest")
def get_latest_vital(patient_id: int, db: Session = Depends(get_db)):
    """Get the most recent vital signs for a patient."""
    vital = db.query(VitalSign).filter(
        VitalSign.patient_id == patient_id
    ).order_by(desc(VitalSign.timestamp)).first()

    if not vital:
        raise HTTPException(status_code=404, detail="No vitals found for this patient")

    return {
        "patient_id": patient_id,
        "timestamp": vital.timestamp.isoformat(),
        "heart_rate": vital.heart_rate,
        "blood_pressure_systolic": vital.blood_pressure_systolic,
        "blood_pressure_diastolic": vital.blood_pressure_diastolic,
        "respiratory_rate": vital.respiratory_rate,
        "spo2": vital.spo2,
        "temperature": vital.temperature,
        "gcs_score": vital.gcs_score,
        "risk_score": vital.risk_score,
        "risk_level": vital.risk_level
    }


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get overall dashboard statistics."""
    total_patients = db.query(Patient).count()
    active_patients = db.query(Patient).filter(Patient.is_active.is_(True)).count()
    critical_patients = db.query(Patient).filter(Patient.status == "critical").count()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_alerts_today = db.query(Alert).filter(Alert.timestamp >= today_start).count()
    unacknowledged = db.query(Alert).filter(Alert.acknowledged == False).count()

    avg_risk = db.query(func.avg(Patient.risk_score)).scalar() or 0.0

    recent_alerts = db.query(Alert).order_by(desc(Alert.timestamp)).limit(10).all()

    return {
        "total_patients": total_patients,
        "active_patients": active_patients,
        "critical_patients": critical_patients,
        "total_alerts_today": total_alerts_today,
        "unacknowledged_alerts": unacknowledged,
        "avg_risk_score": round(float(avg_risk), 4),
        "recent_alerts": recent_alerts
    }


@router.get("/dashboard/risk-distribution")
def get_risk_distribution(db: Session = Depends(get_db)):
    """Get risk score distribution across all patients."""
    latest_ids = (
        db.query(func.max(VitalSign.id))
        .group_by(VitalSign.patient_id)
        .subquery()
    )
    latest_vitals = db.query(VitalSign).filter(VitalSign.id.in_(latest_ids)).all()

    distribution = {"stable": 0, "moderate": 0, "critical": 0}
    for v in latest_vitals:
        if v.risk_level in distribution:
            distribution[v.risk_level] += 1

    return distribution


# ============== WebSocket Endpoints ==============

@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates."""
    await manager.connect_dashboard(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            try:
                message = __import__("json").loads(data)
                if message.get("action") == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "data": {},
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                elif message.get("action") == "stats":
                    stats = manager.get_connection_stats()
                    await manager.send_personal_message({
                        "type": "connection_stats",
                        "data": stats,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


@router.websocket("/ws/patient/{patient_id}")
async def patient_websocket(websocket: WebSocket, patient_id: int):
    """WebSocket endpoint for monitoring a specific patient."""
    await manager.connect_patient(websocket, patient_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = __import__("json").loads(data)
                if message.get("action") == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "data": {},
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
