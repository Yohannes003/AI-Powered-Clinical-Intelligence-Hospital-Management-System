from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional
from datetime import datetime

from app.models.models import AIPrediction, ClinicalDigitalTwin, ClinicalAlert, RiskLevel
from app.ai_engine.engine import get_ai_engine
from app.services.patient_service import PatientService
from app.db.session import safe_get_icu_db
from app.models.models import Patient
from sqlalchemy import insert
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService
from loguru import logger

import json
from datetime import datetime as _dt

def _safe_val(v):
    if isinstance(v, _dt): return v.isoformat()
    return v

def _safe_dict(d):
    if not isinstance(d, dict): return d
    return {k: _safe_val(v) for k, v in d.items()}



class AIService:

    @staticmethod
    async def run_full_assessment(
        db: AsyncSession,
        patient_id,
        triggered_by_id: int
    ) -> dict:
        """
        Complete AI pipeline:
        1. Load patient data
        2. Run AI engine
        3. Persist prediction
        4. Update digital twin
        5. Generate alerts
        6. Publish events
        7. Audit log
        """
        # Load patient with all clinical data
        icu_shadow_created = False
        # Handle ICU-origin patients (ids like 'icu-123') by creating or locating a shadow Patient
        if isinstance(patient_id, str) and patient_id.startswith('icu-'):
            icu_db = await safe_get_icu_db()
            if icu_db is None:
                raise ValueError("ICU database not available for AI assessment")
            icu_int = int(patient_id.split('-')[1])
            # Try find existing shadow patient by MRN 'ICU-<id>'
            existing = await db.execute(select(Patient).where(Patient.patient_id == f"ICU-{icu_int}"))
            patient = existing.scalar_one_or_none()
            if not patient:
                # Fetch basic info from ICU
                q = "SELECT id, name, admission_date, gender, bed_number, status, created_at FROM patients WHERE id = :id"
                row = await icu_db.execute(text(q), {"id": icu_int})
                r = row.fetchone()
                if not r:
                    raise ValueError(f"ICU patient {patient_id} not found")
                # Create a minimal shadow Patient (date_of_birth required) — use placeholder DOB
                from datetime import datetime as _dt
                placeholder_dob = _dt(1900, 1, 1)
                patient = Patient(
                    patient_id=f"ICU-{r.id}",
                    full_name=r.name or f"ICU Patient {r.id}",
                    date_of_birth=placeholder_dob,
                    gender=(r.gender or 'Other'),
                    status='icu',
                    admission_date=r.admission_date if hasattr(r, 'admission_date') else None,
                )
                db.add(patient)
                await db.flush()
                icu_shadow_created = True
        else:
            patient = await PatientService.get_by_id(db, int(patient_id))
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

        # Serialize for AI engine
        if isinstance(patient_id, str) and patient_id.startswith('icu-'):
            # Build patient dict from ICU shadow (and ICU DB rows)
            patient_dict = {
                "id": patient.id,
                "full_name": patient.full_name,
                "date_of_birth": patient.date_of_birth,
                "gender": patient.gender,
                "allergies": [],
                "current_medications": [],
                "chronic_conditions": [],
            }
            vitals_list = []
            diagnoses_list = []
            labs_list = []
            icu_db = await safe_get_icu_db()
            if icu_db:
                try:
                    qv = text("SELECT id, temperature, heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2, gcs_score, timestamp as recorded_at FROM vital_signs WHERE patient_id = :id ORDER BY timestamp DESC LIMIT 10")
                    rows = await icu_db.execute(qv, {"id": int(patient_id.split('-')[1])})
                    for r in rows.fetchall():
                        vitals_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                try:
                    qd = text("SELECT id, condition_name, severity, diagnosed_at FROM diagnoses WHERE patient_id = :id")
                    rows = await icu_db.execute(qd, {"id": int(patient_id.split('-')[1])})
                    for r in rows.fetchall():
                        diagnoses_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                try:
                    ql = text("SELECT id, test_name, results, resulted_at FROM lab_results WHERE patient_id = :id")
                    rows = await icu_db.execute(ql, {"id": int(patient_id.split('-')[1])})
                    for r in rows.fetchall():
                        labs_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                await icu_db.close()
        else:
            patient_dict = {
                "id": patient.id,
                "full_name": patient.full_name,
                "date_of_birth": patient.date_of_birth,
                "gender": patient.gender,
                "allergies": patient.allergies or [],
                "current_medications": patient.current_medications or [],
                "chronic_conditions": patient.chronic_conditions or [],
            }

            vitals_list = [
                _safe_dict({c.name: getattr(v, c.name) for c in v.__table__.columns})
                for v in sorted(patient.vitals, key=lambda x: x.recorded_at or datetime.min)[-10:]
            ]

            diagnoses_list = [
                _safe_dict({c.name: getattr(d, c.name) for c in d.__table__.columns})
                for d in patient.diagnoses
            ]

            labs_list = [
                _safe_dict({c.name: getattr(l, c.name) for c in l.__table__.columns})
                for l in patient.lab_results
            ]

        # Run AI assessment
        engine = get_ai_engine()
        assessment = await engine.full_assessment(patient_dict, vitals_list, diagnoses_list, labs_list)

        risk = assessment["risk_assessment"]

        # Persist AI Prediction
        prediction = AIPrediction(
            patient_id=patient.id,
            created_by_id=triggered_by_id,
            prediction_type="full_risk_assessment",
            risk_score=risk["risk_score"],
            risk_level=RiskLevel(risk["risk_level"]) if risk["risk_level"] in ("stable", "moderate", "critical", "low", "medium", "high") else RiskLevel.MODERATE,
            confidence_score=risk["confidence_score"],
            explanation=risk["explanation"],
            contributing_factors=risk["contributing_factors"],
            contradictions=risk.get("contradictions", []),
            recommendations=risk.get("recommendations", []),
            model_version=risk.get("model_version"),
            requires_review=risk.get("requires_human_review", False),
            input_snapshot={
                "vitals_count": len(vitals_list),
                "diagnoses_count": len(diagnoses_list),
                "labs_count": len(labs_list),
            }
        )
        db.add(prediction)
        await db.flush()

        # Update / Create Digital Twin
        twin_data = assessment["digital_twin"]
        existing_twin = await db.execute(
            select(ClinicalDigitalTwin).where(ClinicalDigitalTwin.patient_id == patient.id)
        )
        twin = existing_twin.scalar_one_or_none()

        if twin:
            twin.current_state = twin_data["physiological_state"]
            twin.disease_trajectory = twin_data["disease_trajectory"]
            twin.treatment_response_model = twin_data["treatment_response"]
            twin.what_if_scenarios = twin_data["what_if_scenarios"]
            twin.model_confidence = twin_data["model_confidence"]
            twin.last_simulation_at = datetime.utcnow()
            twin.simulation_count = (twin.simulation_count or 0) + 1
            twin.updated_at = datetime.utcnow()
        else:
            twin = ClinicalDigitalTwin(
                patient_id=patient.id,
                current_state=twin_data["physiological_state"],
                disease_trajectory=twin_data["disease_trajectory"],
                treatment_response_model=twin_data["treatment_response"],
                what_if_scenarios=twin_data["what_if_scenarios"],
                model_confidence=twin_data["model_confidence"],
                last_simulation_at=datetime.utcnow(),
                simulation_count=1,
            )
            db.add(twin)

        # Persist Alerts
        for alert_data in assessment.get("alerts_generated", []):
            alert = ClinicalAlert(
                patient_id=patient.id,
                alert_type=alert_data.get("type"),
                severity=alert_data.get("severity"),
                title=alert_data.get("title"),
                message=alert_data.get("message"),
                source="ai_engine"
            )
            db.add(alert)

        await db.flush()

        # Publish events
        await publish_event(
            EventType.AI_PREDICTION_MADE,
            aggregate_type="Patient",
            aggregate_id=str(patient.id),
            payload={
                "prediction_id": prediction.id,
                "risk_level": risk["risk_level"],
                "risk_score": risk["risk_score"],
                "requires_review": risk.get("requires_human_review"),
                "origin": patient_dict.get("id") if isinstance(patient_id, str) and patient_id.startswith('icu-') else None
            }
        )

        if assessment["anomaly_detection"]["is_anomaly"]:
            await publish_event(
                EventType.AI_ANOMALY_DETECTED,
                aggregate_type="Patient",
                aggregate_id=str(patient.id),
                payload=assessment["anomaly_detection"]
            )

        if risk.get("requires_human_review"):
            await publish_event(
                EventType.HUMAN_REVIEW_REQUIRED,
                aggregate_type="AIPrediction",
                aggregate_id=str(prediction.id),
                payload={"patient_id": patient.id, "confidence": risk["confidence_score"]}
            )

        # Audit
        await AuditService.log(
            db, action="ai.assessment.run",
            user_id=triggered_by_id,
            resource_type="patient",
            resource_id=str(patient.id),
            event_type=EventType.AI_PREDICTION_MADE,
            new_values={"risk_level": risk["risk_level"], "risk_score": risk["risk_score"]}
        )

        assessment["prediction_id"] = prediction.id
        return assessment

    @staticmethod
    async def get_patient_predictions(db: AsyncSession, patient_id: int, limit: int = 10):
        result = await db.execute(
            select(AIPrediction)
            .where(AIPrediction.patient_id == patient_id)
            .order_by(AIPrediction.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_pending_reviews(db: AsyncSession, limit: int = 20):
        result = await db.execute(
            select(AIPrediction)
            .where(AIPrediction.requires_review == True, AIPrediction.reviewed_at == None)
            .order_by(AIPrediction.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def submit_review(
        db: AsyncSession,
        prediction_id: int,
        reviewer_id: int,
        review_notes: str
    ) -> AIPrediction:
        result = await db.execute(
            select(AIPrediction).where(AIPrediction.id == prediction_id)
        )
        prediction = result.scalar_one_or_none()
        if not prediction:
            raise ValueError(f"Prediction {prediction_id} not found")

        prediction.reviewed_by_id = reviewer_id
        prediction.review_notes = review_notes
        prediction.reviewed_at = datetime.utcnow()

        await db.flush()
        return prediction
