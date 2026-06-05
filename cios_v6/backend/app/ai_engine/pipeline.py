"""
3-Stage Clinical AI Pipeline:
1. AI/ML Model → Clinical Report (risk assessment, anomaly detection, digital twin)
2. LLM → Deep reasoning & natural language analysis
3. GenAI (Ground Truth) → Validates against guidelines, produces clinical reality

All stages are bounded by health guidelines defined in guidelines.py
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.ai_engine.engine import get_ai_engine
from app.ai_engine.genai_engine import get_genai_engine, GroundTruthOutput
from app.ai_engine.guidelines import check_guideline_compliance, check_vital_safety
from app.models.models import Patient, GroundTruthRecord
from app.services.patient_service import PatientService
from app.db.session import safe_get_icu_db
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService
from sqlalchemy import text


def _safe_val(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _safe_dict(d):
    if not isinstance(d, dict):
        return d
    return {k: _safe_val(v) for k, v in d.items()}


class ClinicalAIPipeline:
    """
    Orchestrates the 3-stage clinical AI pipeline.
    """

    @staticmethod
    async def run_pipeline(
        db: AsyncSession,
        patient_id,
        triggered_by_id: int,
    ) -> dict:
        icu_shadow_created = False

        # ── Load Patient Data ──────────────────────────────────
        if isinstance(patient_id, str) and patient_id.startswith('icu-'):
            icu_db = await safe_get_icu_db()
            if icu_db is None:
                raise ValueError("ICU database not available")
            icu_int = int(patient_id.split('-')[1])
            existing = await db.execute(select(Patient).where(Patient.patient_id == f"ICU-{icu_int}"))
            patient = existing.scalar_one_or_none()
            if not patient:
                q = "SELECT id, name, admission_date, gender, bed_number, status FROM patients WHERE id = :id"
                row = await icu_db.execute(text(q), {"id": icu_int})
                r = row.fetchone()
                if not r:
                    raise ValueError(f"ICU patient {patient_id} not found")
                placeholder_dob = datetime(1900, 1, 1)
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

        # ── Serialize patient data for AI engines ──────────────
        vitals_list = []
        diagnoses_list = []
        labs_list = []
        patient_dict = {}

        if isinstance(patient_id, str) and patient_id.startswith('icu-'):
            patient_dict = {
                "id": patient.id, "full_name": patient.full_name,
                "date_of_birth": patient.date_of_birth, "gender": patient.gender,
                "allergies": [], "current_medications": [], "chronic_conditions": [],
            }
            icu_db = await safe_get_icu_db()
            if icu_db:
                icu_int = int(patient_id.split('-')[1])
                try:
                    qv = text("SELECT id, temperature, heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2, gcs_score, timestamp as recorded_at FROM vital_signs WHERE patient_id = :id ORDER BY timestamp DESC LIMIT 10")
                    rows = await icu_db.execute(qv, {"id": icu_int})
                    for r in rows.fetchall():
                        vitals_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                try:
                    qd = text("SELECT id, condition_name, severity, diagnosed_at FROM diagnoses WHERE patient_id = :id")
                    rows = await icu_db.execute(qd, {"id": icu_int})
                    for r in rows.fetchall():
                        diagnoses_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                try:
                    ql = text("SELECT id, test_name, results, resulted_at FROM lab_results WHERE patient_id = :id")
                    rows = await icu_db.execute(ql, {"id": icu_int})
                    for r in rows.fetchall():
                        labs_list.append(_safe_dict(dict(r._mapping)))
                except Exception:
                    pass
                await icu_db.close()
        else:
            patient_dict = {
                "id": patient.id, "full_name": patient.full_name,
                "date_of_birth": patient.date_of_birth, "gender": patient.gender,
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

        # ══════════════════════════════════════════════════════════
        # STAGE 1: AI/ML Model → Clinical Report
        # ══════════════════════════════════════════════════════════
        engine = get_ai_engine()
        ai_ml_assessment = await engine.full_assessment(
            patient_dict, vitals_list, diagnoses_list, labs_list
        )
        risk = ai_ml_assessment.get("risk_assessment", {})

        # Check guideline compliance for AI/ML output
        guideline_compliance = check_guideline_compliance(
            risk.get("risk_level", "low"),
            risk.get("confidence_score", 0.0),
        )

        ai_ml_report = {
            "risk_assessment": risk,
            "anomaly_detection": ai_ml_assessment.get("anomaly_detection", {}),
            "clinical_summary": ai_ml_assessment.get("clinical_summary", ""),
            "digital_twin": ai_ml_assessment.get("digital_twin", {}),
            "guideline_compliance": guideline_compliance,
        }

        # ══════════════════════════════════════════════════════════
        # STAGE 2: LLM Reasoning
        # ══════════════════════════════════════════════════════════
        llm_analysis = ai_ml_assessment.get("clinical_summary", "")

        # ══════════════════════════════════════════════════════════
        # STAGE 3: GenAI Ground Truth
        # ══════════════════════════════════════════════════════════
        genai = get_genai_engine()
        ground_truth = await genai.generate_ground_truth(
            patient_dict, ai_ml_report, llm_analysis,
            vitals_list, diagnoses_list, labs_list,
        )

        # ── Persist Ground Truth Record ──────────────────────
        ground_truth_record = GroundTruthRecord(
            patient_id=patient.id,
            created_by_id=triggered_by_id,
            ground_truth_summary=ground_truth.ground_truth_summary,
            ai_ml_report_accuracy=ground_truth.ai_ml_report_accuracy,
            llm_reasoning_quality=ground_truth.llm_reasoning_quality,
            overall_confidence=ground_truth.overall_confidence,
            discrepancies_found=ground_truth.discrepancies_found,
            corrected_recommendations=ground_truth.corrected_recommendations,
            guideline_citations=ground_truth.guideline_citations,
            ai_ml_snapshot=ai_ml_report,
        )
        db.add(ground_truth_record)
        await db.flush()

        # ── Publish Events ───────────────────────────────────
        await publish_event(
            EventType.AI_PIPELINE_COMPLETED,
            aggregate_type="Patient",
            aggregate_id=str(patient.id),
            payload={
                "ground_truth_id": ground_truth_record.id,
                "risk_level": risk.get("risk_level"),
                "overall_confidence": ground_truth.overall_confidence,
            }
        )

        await AuditService.log(
            db, action="ai.pipeline.run",
            user_id=triggered_by_id,
            resource_type="patient",
            resource_id=str(patient.id),
            event_type=getattr(EventType, "AI_PIPELINE_COMPLETED", None),
            new_values={
                "risk_level": risk.get("risk_level"),
                "ground_truth_confidence": ground_truth.overall_confidence,
            }
        )

        return {
            "pipeline_id": ground_truth_record.id,
            "patient_id": patient.id,
            "stage_1_ai_ml": ai_ml_report,
            "stage_2_llm": {"clinical_summary": llm_analysis},
            "stage_3_ground_truth": ground_truth.to_dict(),
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def get_pipeline_results(
        db: AsyncSession, patient_id: int, limit: int = 5
    ) -> List[GroundTruthRecord]:
        result = await db.execute(
            select(GroundTruthRecord)
            .where(GroundTruthRecord.patient_id == patient_id)
            .order_by(GroundTruthRecord.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
