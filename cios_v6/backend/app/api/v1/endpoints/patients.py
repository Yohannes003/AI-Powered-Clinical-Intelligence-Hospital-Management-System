from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db, safe_get_icu_db
from sqlalchemy import text
from app.core.security import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.patient_service import PatientService
from app.services.ai_service import AIService
from app.services.clinical_validation import validate_vitals, ValidationResult
from app.ai_engine.clinical_scores import compute_both
from app.audit.audit_service import AuditService
from app.events.event_bus import publish_event, EventType
from app.models.models import Patient as PatientModel, PatientStatus

router = APIRouter(prefix="/patients", tags=["Patients"])


class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: datetime
    gender: str
    blood_type: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[dict] = None
    allergies: Optional[List[str]] = []
    chronic_conditions: Optional[List[str]] = []
    current_medications: Optional[List[str]] = []
    insurance_info: Optional[dict] = None
    ward: Optional[str] = None
    bed_number: Optional[str] = None
    attending_doctor_id: Optional[int] = None
    status: str = "active"


class PatientUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {s.value for s in PatientStatus if s.value != "deceased"}
        if v not in valid:
            raise ValueError(f"Status must be one of: {', '.join(valid)}")
        return v


class VitalSignCreate(BaseModel):
    temperature: Optional[float] = None
    heart_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[float] = None
    blood_glucose: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    gcs_score: Optional[int] = None
    pain_score: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("temperature", "heart_rate", "systolic_bp", "diastolic_bp",
                     "respiratory_rate", "oxygen_saturation", "blood_glucose",
                     "gcs_score", "pain_score", mode="before")
    @classmethod
    def validate_physiological(cls, v, info):
        if v is None:
            return v
        data = {info.field_name: v}
        result = validate_vitals(data)
        if not result.passed:
            raise ValueError(result.errors[0])
        return v



def serialize_patient(p) -> dict:
    return {
        "id": p.id, "patient_id": p.patient_id, "full_name": p.full_name,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "gender": p.gender, "blood_type": p.blood_type,
        "contact_phone": p.contact_phone, "contact_email": p.contact_email,
        "address": p.address, "allergies": p.allergies,
        "chronic_conditions": p.chronic_conditions, "current_medications": p.current_medications,
        "status": p.status, "ward": p.ward, "bed_number": p.bed_number,
        "attending_doctor_id": p.attending_doctor_id,
        "admission_date": p.admission_date.isoformat() if p.admission_date else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.post("/", status_code=201)
async def create_patient(
    body: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PATIENT_CREATE))
):
    patient = await PatientService.create(db, body.dict(), created_by_id=current_user.id)
    return {"message": "Patient created", "patient": serialize_patient(patient)}


@router.get("/")
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PATIENT_VIEW))
):
    patients, total = await PatientService.list_patients(db, skip, limit, search, status)

    result_list = [serialize_patient(p) for p in patients]

    # If ICU DB available, fetch ICU patients and merge
    icu_db = await safe_get_icu_db()
    if icu_db is not None:
        try:
            q = text("SELECT id, name, admission_date, gender, bed_number, status, risk_score, created_at FROM patients ORDER BY created_at DESC LIMIT :limit OFFSET :skip")
            icu_rows = await icu_db.execute(q, {"limit": limit, "skip": skip})
            icu_rows = icu_rows.fetchall()
            for r in icu_rows:
                mapped = {
                    "id": f"icu-{r.id}",
                    "patient_id": f"ICU-{r.id}",
                    "full_name": r.name,
                    "date_of_birth": None,
                    "gender": r.gender,
                    "blood_type": None,
                    "contact_phone": None,
                    "contact_email": None,
                    "address": None,
                    "allergies": [],
                    "chronic_conditions": [],
                    "current_medications": [],
                    "status": 'icu' if r.status in ('critical','stable','recovered') else r.status,
                    "ward": 'ICU',
                    "bed_number": r.bed_number,
                    "attending_doctor_id": None,
                    "admission_date": r.admission_date.isoformat() if r.admission_date else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                result_list.append(mapped)
            try:
                icu_count = await icu_db.execute(text("SELECT count(*) FROM patients"))
                icu_total = icu_count.scalar()
                total = (total or 0) + (icu_total or 0)
            except Exception:
                pass
        finally:
            await icu_db.close()

    return {"total": total, "skip": skip, "limit": limit, "patients": result_list}


@router.get("/dashboard/stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.SYSTEM_STATS))
):
    return await PatientService.get_dashboard_stats(db)


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PATIENT_VIEW))
):
    # If ICU-sourced patient (id prefixed with 'icu-'), proxy read from ICU DB
    if isinstance(patient_id, str) and patient_id.startswith('icu-'):
        icu_db = await safe_get_icu_db()
        if icu_db is None:
            raise HTTPException(status_code=404, detail="ICU database not available")
        try:
            try:
                icu_int = int(patient_id.split('-')[1])
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ICU patient id")
            q = text("SELECT id, name, admission_date, gender, bed_number, status, risk_score, created_at, diagnosis FROM patients WHERE id = :id")
            row = await icu_db.execute(q, {"id": icu_int})
            r = row.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="ICU patient not found")
            mapped = {
                "id": f"icu-{r.id}",
                "patient_id": f"ICU-{r.id}",
                "full_name": r.name,
                "date_of_birth": None,
                "gender": r.gender,
                "blood_type": None,
                "contact_phone": None,
                "contact_email": None,
                "address": None,
                "allergies": [],
                "chronic_conditions": [],
                "current_medications": [],
                "diagnosis": r.diagnosis,
                "status": 'icu' if r.status in ('critical','stable','recovered') else r.status,
                "ward": 'ICU',
                "bed_number": r.bed_number,
                "attending_doctor_id": None,
                "admission_date": r.admission_date.isoformat() if r.admission_date else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            await AuditService.log(db, action="patient.view", user_id=current_user.id,
                                   resource_type="patient", resource_id=str(patient_id))
            return mapped
        finally:
            await icu_db.close()

    # Otherwise normal CIOS patient (numeric id expected)
    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient id")
    patient = await PatientService.get_by_id(db, pid)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    await AuditService.log(db, action="patient.view", user_id=current_user.id,
                           resource_type="patient", resource_id=str(pid))
    return serialize_patient(patient)


@router.put("/{patient_id}")
async def update_patient(
    patient_id: str,
    body: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PATIENT_EDIT))
):
    if isinstance(patient_id, str) and patient_id.startswith('icu-'):
        raise HTTPException(status_code=400, detail="Cannot update ICU patient status from CIOS")

    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient id")

    patient = await PatientService.update_status(db, pid, body.status, current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    result = {"message": "Patient updated", "patient": serialize_patient(patient)}

    # If discharging, auto-generate a discharge report
    if body.status == "discharged":
        try:
            from app.reporting.report_service import ReportingService
            report_svc = ReportingService()
            patient_dict = {c.name: getattr(patient, c.name) for c in patient.__table__.columns}
            vitals_list = [{c.name: getattr(v, c.name) for c in v.__table__.columns}
                          for v in sorted(patient.vitals, key=lambda x: x.recorded_at or datetime.min)]
            diagnoses_list = [{c.name: getattr(d, c.name) for c in d.__table__.columns}
                             for d in patient.diagnoses]
            labs_list = [{c.name: getattr(l, c.name) for c in l.__table__.columns}
                        for l in patient.lab_results]

            from app.services.ai_service import AIService
            ai_assessment = {}
            try:
                ai_assessment = await AIService.run_full_assessment(db, str(pid), current_user.id)
            except Exception:
                ai_assessment = {"risk_assessment": {}, "clinical_summary": "AI assessment unavailable"}

            file_path = report_svc.generate_patient_report(
                patient=patient_dict, vitals=vitals_list, diagnoses=diagnoses_list,
                labs=labs_list, ai_assessment=ai_assessment, format="pdf",
                generated_by=current_user.full_name
            )

            from app.models.models import Report
            import uuid as _uuid
            report = Report(
                report_id=str(_uuid.uuid4())[:12].upper(),
                report_type="discharge_summary",
                title=f"Discharge Summary — {patient.full_name}",
                patient_id=patient.id,
                generated_by_id=current_user.id,
                format="pdf",
                file_path=file_path,
                ai_summary=ai_assessment.get("clinical_summary", ""),
            )
            db.add(report)
            await db.flush()

            result["report"] = {
                "report_id": report.report_id,
                "report_db_id": report.id,
                "download_url": f"/api/v1/reports/download/{report.id}",
                "format": "pdf",
            }
            await AuditService.log(db, action="patient.discharge", user_id=current_user.id,
                                   resource_type="patient", resource_id=str(pid),
                                   new_values={"status": "discharged", "report_id": report.report_id})
        except Exception as e:
            result["report_warning"] = f"Discharge report generation failed: {str(e)}"

    # If moving to ICU, sync patient to the ICU monitoring database
    if body.status == "icu":
        try:
            icu_db = await safe_get_icu_db()
            if icu_db is not None:
                q = text("SELECT id FROM patients WHERE id = :id")
                row = await icu_db.execute(q, {"id": pid})
                existing = row.fetchone()
                if existing:
                    q = text("UPDATE patients SET name = :name, gender = :gender, status = :status WHERE id = :id")
                    await icu_db.execute(q, {"id": pid, "name": patient.full_name, "gender": patient.gender, "status": "stable"})
                else:
                    q = text("INSERT INTO patients (name, gender, bed_number, status, admission_date) VALUES (:name, :gender, :bed, :status, :adm)")
                    await icu_db.execute(q, {"name": patient.full_name, "gender": patient.gender or "Other", "bed": patient.bed_number or f"CIOS-{pid}", "status": "stable", "adm": datetime.utcnow()})
                await icu_db.commit()
                result["icu_sync"] = "Patient added to ICU monitoring system"
                await AuditService.log(db, action="patient.icu_admit", user_id=current_user.id,
                                       resource_type="patient", resource_id=str(pid),
                                       new_values={"status": "icu"})
        except Exception as e:
            result["icu_sync_warning"] = f"ICU sync failed: {str(e)}"
        finally:
            if icu_db:
                await icu_db.close()

    return result


@router.post("/{patient_id}/vitals", status_code=201)
async def record_vitals(
    patient_id: str,
    body: VitalSignCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.VITALS_RECORD))
):
    # If ICU patient, forward vitals to ICU DB
    if isinstance(patient_id, str) and patient_id.startswith('icu-'):
        icu_db = await safe_get_icu_db()
        if icu_db is None:
            raise HTTPException(status_code=404, detail="ICU database not available")
        try:
            try:
                icu_int = int(patient_id.split('-')[1])
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ICU patient id")

            data = body.dict(exclude_none=True)
            data['patient_id'] = icu_int
            field_map = {'systolic_bp': 'blood_pressure_systolic', 'diastolic_bp': 'blood_pressure_diastolic', 'oxygen_saturation': 'spo2'}
            for old_key, new_key in field_map.items():
                if old_key in data:
                    data[new_key] = data.pop(old_key)

            inserted_id = None
            for table in ('vital_signs', 'vitals'):
                try:
                    cols = ', '.join(data.keys())
                    vals = ', '.join(':' + k for k in data.keys())
                    sql = f"INSERT INTO {table} ({cols}) VALUES ({vals}) RETURNING id"
                    res = await icu_db.execute(text(sql), data)
                    try:
                        inserted_id = res.scalar()
                    except Exception:
                        row = res.fetchone()
                        if row:
                            inserted_id = row[0]
                    if inserted_id:
                        break
                except Exception:
                    continue

            if not inserted_id:
                raise HTTPException(status_code=500, detail="Failed to record vitals in ICU database")

            is_critical = False
            hr = data.get('heart_rate')
            spo2 = data.get('spo2')
            sys_bp = data.get('blood_pressure_systolic')
            temp = data.get('temperature')
            gcs = data.get('gcs_score')
            if hr and (hr < 40 or hr > 150):
                is_critical = True
            if spo2 and spo2 < 90:
                is_critical = True
            if sys_bp and (sys_bp < 80 or sys_bp > 180):
                is_critical = True
            if temp and (temp < 35 or temp > 40):
                is_critical = True
            if gcs and gcs < 13:
                is_critical = True

            try:
                await publish_event(
                    EventType.VITALS_RECORDED,
                    aggregate_type="patient",
                    aggregate_id=f"icu-{icu_int}",
                    payload={"patient_id": f"icu-{icu_int}", "vital_id": inserted_id, "values": data, "is_critical": is_critical}
                )
            except Exception:
                pass

            return {"vital_id": inserted_id, "is_critical": is_critical, "ai_triggered": False}
        finally:
            await icu_db.close()

    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient id")

    vital_data = body.model_dump(exclude_none=True)
    validation = validate_vitals(vital_data)
    vital_data = validation.normalized

    vital = await PatientService.record_vitals(
        db, pid, vital_data, current_user.id
    )
    result = {"vital_id": vital.id, "is_critical": vital.is_critical, "ai_triggered": False}

    early_warning_scores = compute_both(vital_data)
    result["mews"] = {
        "total_score": early_warning_scores[0].total_score,
        "risk_level": early_warning_scores[0].risk_level,
        "clinical_response": early_warning_scores[0].clinical_response,
        "components": early_warning_scores[0].score_components,
    }
    result["news2"] = {
        "total_score": early_warning_scores[1].total_score,
        "risk_level": early_warning_scores[1].risk_level,
        "clinical_response": early_warning_scores[1].clinical_response,
        "components": early_warning_scores[1].score_components,
    }

    if validation.warnings:
        result["validation_warnings"] = validation.warnings

    # Only doctors and admins trigger AI on vitals
    from app.core.permissions import has_permission
    if has_permission(current_user.role, Permission.AI_ASSESS):
        try:
            assessment = await AIService.run_full_assessment(db, patient_id, current_user.id)
            result["ai_triggered"]  = True
            result["risk_level"]    = assessment["risk_assessment"]["risk_level"]
            result["risk_score"]    = assessment["risk_assessment"]["risk_score"]
        except Exception:
            pass
    return result


@router.get("/{patient_id}/vitals")
async def get_vitals(
    patient_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.VITALS_VIEW))
):
    # ICU patient vitals: attempt to read from ICU DB if configured
    if isinstance(patient_id, str) and patient_id.startswith('icu-'):
        icu_db = await safe_get_icu_db()
        if icu_db is None:
            raise HTTPException(status_code=404, detail="ICU database not available")
        try:
            try:
                icu_int = int(patient_id.split('-')[1])
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid ICU patient id")
            for table in ('vital_signs', 'vitals'):
                try:
                    q = text(f"SELECT id, temperature, heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2, gcs_score, timestamp as recorded_at FROM {table} WHERE patient_id = :id ORDER BY timestamp DESC LIMIT :limit")
                    rows = await icu_db.execute(q, {"id": icu_int, "limit": limit})
                    rows = rows.fetchall()
                    if rows:
                        mapped = []
                        for r in rows:
                            d = dict(r._mapping)
                            d["systolic_bp"] = d.pop("blood_pressure_systolic", None)
                            d["diastolic_bp"] = d.pop("blood_pressure_diastolic", None)
                            d["oxygen_saturation"] = d.pop("spo2", None)
                            d["timestamp"] = d.pop("recorded_at", d.get("timestamp"))
                            mapped.append(d)
                        return {"patient_id": patient_id, "vitals": mapped}
                except Exception:
                    continue
            return {"patient_id": patient_id, "vitals": []}
        finally:
            await icu_db.close()

    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient id")

    vitals = await PatientService.get_patient_vitals(db, pid, limit)
    return {"patient_id": pid,
            "vitals": [{c.name: getattr(v, c.name) for c in v.__table__.columns} for v in vitals]}


@router.get("/{patient_id}/audit-trail")
async def get_audit_trail(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.AUDIT_VIEW_OWN))
):
    # For ICU patients there is no centralized audit trail in CIOS; return empty
    if isinstance(patient_id, str) and patient_id.startswith('icu-'):
        return {"patient_id": patient_id, "audit_trail": []}

    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient id")

    logs = await AuditService.get_patient_audit_trail(db, pid)
    return {"patient_id": pid,
            "audit_trail": [{"id": l.id, "action": l.action, "user_id": l.user_id,
                              "timestamp": l.timestamp.isoformat(), "status": l.status}
                            for l in logs]}
