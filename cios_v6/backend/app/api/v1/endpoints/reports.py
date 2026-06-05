from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os, uuid, io

from app.db.session import get_db, safe_get_icu_db
from app.core.security import get_current_user, decode_token
from app.services.patient_service import PatientService
from app.services.ai_service import AIService
from app.reporting.report_service import ReportingService
from app.models.models import Report, Patient
from app.audit.audit_service import AuditService
from app.events.event_bus import publish_event, EventType

router = APIRouter(prefix="/reports", tags=["Reports"])
report_svc = ReportingService()


class ReportRequest(BaseModel):
    patient_id: str
    format: str = "pdf"   # pdf | csv | excel | xps
    include_ai: bool = True


# ── Generate Report ──────────────────────────────────────

@router.post("/generate")
async def generate_report(
    body: ReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if body.format not in ("pdf", "csv", "excel", "xlsx", "xps"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")

    def safe(v):
        return v.isoformat() if isinstance(v, datetime) else v

    patient = None
    patient_dict = {}
    vitals_list = []
    diagnoses_list = []
    labs_list = []

    if isinstance(body.patient_id, str) and body.patient_id.startswith('icu-'):
        icu_db = await safe_get_icu_db()
        if icu_db is None:
            raise HTTPException(status_code=503, detail="ICU database not available")
        try:
            icu_int = int(body.patient_id.split('-')[1])
            q = text("SELECT id, name, admission_date, gender, bed_number, status, risk_score, created_at, diagnosis FROM patients WHERE id = :id")
            row = await icu_db.execute(q, {"id": icu_int})
            r = row.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="ICU patient not found")
            patient_dict = {
                "full_name": r.name or f"ICU Patient {r.id}",
                "patient_id": f"ICU-{r.id}",
                "gender": r.gender or "Other",
                "status": r.status or "icu",
                "ward": "ICU",
                "bed_number": r.bed_number or "",
                "admission_date": safe(r.admission_date) if r.admission_date else None,
            }
            try:
                qv = text("SELECT id, temperature, heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2, gcs_score, timestamp as recorded_at FROM vital_signs WHERE patient_id = :id ORDER BY timestamp DESC LIMIT 50")
                rows = await icu_db.execute(qv, {"id": icu_int})
                for vrow in rows.fetchall():
                    vitals_list.append(dict(vrow._mapping))
            except Exception:
                pass
            try:
                qd = text("SELECT id, condition_name, severity, diagnosed_at FROM diagnoses WHERE patient_id = :id")
                rows = await icu_db.execute(qd, {"id": icu_int})
                for drow in rows.fetchall():
                    diagnoses_list.append(dict(drow._mapping))
            except Exception:
                pass
        finally:
            await icu_db.close()

        existing = await db.execute(select(Patient).where(Patient.patient_id == f"ICU-{icu_int}"))
        patient = existing.scalar_one_or_none()
        if not patient:
            from datetime import datetime as _dt
            placeholder_dob = _dt(1900, 1, 1)
            patient = Patient(
                patient_id=f"ICU-{icu_int}",
                full_name=patient_dict.get("full_name", f"ICU Patient {icu_int}"),
                date_of_birth=placeholder_dob,
                gender=patient_dict.get("gender", "Other"),
                status="icu",
            )
            db.add(patient)
            await db.flush()
    else:
        try:
            pid = int(body.patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient ID")
        patient = await PatientService.get_by_id(db, pid)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_dict = {c.name: safe(getattr(patient, c.name)) for c in patient.__table__.columns}
        vitals_list = [{c.name: safe(getattr(v, c.name)) for c in v.__table__.columns}
                       for v in sorted(patient.vitals, key=lambda x: x.recorded_at or datetime.min)]
        diagnoses_list = [{c.name: safe(getattr(d, c.name)) for c in d.__table__.columns}
                          for d in patient.diagnoses]
        labs_list = [{c.name: safe(getattr(l, c.name)) for c in l.__table__.columns}
                     for l in patient.lab_results]

    ai_assessment = {}
    patient_name = patient_dict.get("full_name", f"Patient {body.patient_id}")
    if body.include_ai:
        try:
            ai_assessment = await AIService.run_full_assessment(db, body.patient_id, current_user.id)
        except Exception:
            ai_assessment = {"risk_assessment": {}, "clinical_summary": "AI assessment unavailable"}

    file_path = report_svc.generate_patient_report(
        patient=patient_dict,
        vitals=vitals_list,
        diagnoses=diagnoses_list,
        labs=labs_list,
        ai_assessment=ai_assessment,
        format=body.format,
        generated_by=current_user.full_name
    )

    report = Report(
        report_id=str(uuid.uuid4())[:12].upper(),
        report_type="patient_full",
        title=f"Clinical Report — {patient_name}",
        patient_id=patient.id if patient else 0,
        generated_by_id=current_user.id,
        format=body.format,
        file_path=file_path,
        ai_summary=ai_assessment.get("clinical_summary", ""),
        parameters={"include_ai": body.include_ai}
    )
    db.add(report)
    await db.flush()

    await publish_event(
        EventType.REPORT_GENERATED,
        aggregate_type="Report",
        aggregate_id=str(report.id),
        payload={"patient_id": body.patient_id, "format": body.format, "report_id": report.report_id}
    )
    await AuditService.log(
        db, action="report.generate",
        user_id=current_user.id,
        resource_type="report",
        resource_id=str(report.id),
        event_type=EventType.REPORT_GENERATED,
        new_values={"format": body.format, "patient_id": body.patient_id}
    )

    file_size = round(os.path.getsize(file_path) / 1024, 1) if os.path.exists(file_path) else 0

    return {
        "message": "Report generated",
        "report_id": report.report_id,
        "report_db_id": report.id,
        "download_url": f"/api/v1/reports/download/{report.id}",
        "format": body.format,
        "file_size_kb": file_size,
    }


# ── Download Report — accepts token as query param ───────
# Browser <a href> links cannot send Authorization headers,
# so we accept ?token=<jwt> as an alternative.

@router.get("/download/{report_id}")
async def download_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    # Primary auth: Bearer header (API / Swagger)
    current_user=Depends(get_current_user),
):
    return await _serve_file(report_id, db)


@router.get("/download/{report_id}/token")
async def download_report_with_token(
    report_id: int,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Download endpoint that accepts token as a query parameter.
    Used by the frontend for direct browser downloads via <a href>.
    """
    # Validate token manually
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    return await _serve_file(report_id, db)


async def _serve_file(report_id: int, db: AsyncSession):
    """Shared file serving logic."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    ext_map = {
        "pdf":   "application/pdf",
        "csv":   "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx":  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xps":   "application/vnd.ms-xpsdocument",
    }
    media_type = ext_map.get(report.format, "application/octet-stream")
    filename   = os.path.basename(report.file_path)

    # Stream the file so it downloads correctly in all browsers
    def file_iterator(path, chunk=65536):
        with open(path, "rb") as f:
            while chunk_data := f.read(chunk):
                yield chunk_data

    return StreamingResponse(
        file_iterator(report.file_path),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(os.path.getsize(report.file_path)),
            "Cache-Control": "no-cache",
        }
    )


# ── List Reports ─────────────────────────────────────────

@router.get("/")
async def list_reports(
    patient_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = select(Report)
    if patient_id:
        query = query.where(Report.patient_id == patient_id)
    result = await db.execute(
        query.order_by(Report.created_at.desc()).offset(skip).limit(limit)
    )
    reports = result.scalars().all()
    return {
        "reports": [
            {c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in reports
        ]
    }
