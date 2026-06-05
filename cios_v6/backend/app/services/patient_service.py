from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
import uuid

from app.models.models import Patient, VitalSign, LabResult, Diagnosis, AIPrediction
from app.events.event_bus import publish_event, EventType
from app.audit.audit_service import AuditService


def generate_mrn() -> str:
    return f"MRN{datetime.utcnow().strftime('%Y%m')}{str(uuid.uuid4().int)[:6]}"


class PatientService:

    @staticmethod
    async def create(db: AsyncSession, data: dict, created_by_id: int) -> Patient:
        patient = Patient(
            patient_id=generate_mrn(),
            **{k: v for k, v in data.items() if hasattr(Patient, k)}
        )
        db.add(patient)
        await db.flush()

        await publish_event(
            EventType.PATIENT_CREATED,
            aggregate_type="Patient",
            aggregate_id=str(patient.id),
            payload={"patient_id": patient.id, "mrn": patient.patient_id, "name": patient.full_name}
        )

        await AuditService.log(
            db, action="patient.create",
            user_id=created_by_id,
            resource_type="patient",
            resource_id=str(patient.id),
            event_type=EventType.PATIENT_CREATED,
            new_values={"name": patient.full_name, "mrn": patient.patient_id}
        )

        return patient

    @staticmethod
    async def update_status(db: AsyncSession, patient_id: int, status: str, updated_by_id: int) -> Optional[Patient]:
        patient = await db.get(Patient, patient_id)
        if not patient:
            return None
        old_status = patient.status
        patient.status = status
        await db.flush()

        await AuditService.log(
            db, action="patient.update_status",
            user_id=updated_by_id,
            resource_type="patient",
            resource_id=str(patient_id),
            event_type=EventType.PATIENT_UPDATED,
            old_values={"status": old_status},
            new_values={"status": status}
        )

        return patient

    @staticmethod
    async def get_by_id(db: AsyncSession, patient_id: int) -> Optional[Patient]:
        result = await db.execute(
            select(Patient)
            .options(
                selectinload(Patient.vitals),
                selectinload(Patient.diagnoses),
                selectinload(Patient.lab_results),
                selectinload(Patient.ai_predictions),
            )
            .where(Patient.id == patient_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_patients(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        doctor_id: Optional[int] = None,
    ) -> tuple[List[Patient], int]:
        query = select(Patient)

        if search:
            query = query.where(
                or_(
                    Patient.full_name.ilike(f"%{search}%"),
                    Patient.patient_id.ilike(f"%{search}%"),
                )
            )
        if status:
            query = query.where(Patient.status == status)
        if doctor_id:
            query = query.where(Patient.attending_doctor_id == doctor_id)

        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar()

        result = await db.execute(
            query.order_by(Patient.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all(), total

    @staticmethod
    async def record_vitals(
        db: AsyncSession,
        patient_id: int,
        vitals_data: dict,
        recorded_by_id: int
    ) -> VitalSign:
        vital = VitalSign(patient_id=patient_id, recorded_by_id=recorded_by_id, **vitals_data)

        # Auto-flag critical values
        vital.is_critical = PatientService._is_critical_vital(vitals_data)

        db.add(vital)
        await db.flush()

        await publish_event(
            EventType.VITALS_RECORDED,
            aggregate_type="Patient",
            aggregate_id=str(patient_id),
            payload={
                "patient_id": patient_id,
                "vital_id": vital.id,
                "is_critical": vital.is_critical,
                "vitals": vitals_data
            }
        )

        return vital

    @staticmethod
    def _is_critical_vital(vitals: dict) -> bool:
        checks = [
            ("temperature", 35.0, 40.0),
            ("heart_rate", 40, 150),
            ("systolic_bp", 70, 200),
            ("oxygen_saturation", 85, 100),
            ("gcs_score", 3, 12),
        ]
        for field, low, high in checks:
            val = vitals.get(field)
            if val is not None:
                if val < low or val > high:
                    return True
        return False

    @staticmethod
    async def get_patient_vitals(
        db: AsyncSession, patient_id: int, limit: int = 20
    ) -> List[VitalSign]:
        result = await db.execute(
            select(VitalSign)
            .where(VitalSign.patient_id == patient_id)
            .order_by(VitalSign.recorded_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> dict:
        total = await db.execute(select(func.count(Patient.id)))
        active = await db.execute(select(func.count(Patient.id)).where(Patient.status == "active"))
        icu = await db.execute(select(func.count(Patient.id)).where(Patient.status == "icu"))
        critical_ai = await db.execute(
            select(func.count(AIPrediction.id))
            .where(AIPrediction.risk_level.in_(["high", "critical"]))
        )
        pending_review = await db.execute(
            select(func.count(AIPrediction.id))
            .where(AIPrediction.requires_review == True, AIPrediction.reviewed_at == None)
        )

        return {
            "total_patients": total.scalar(),
            "active_patients": active.scalar(),
            "icu_patients": icu.scalar(),
            "high_risk_predictions": critical_ai.scalar(),
            "pending_reviews": pending_review.scalar(),
        }
