"""
API routes for AI-generated clinical reports.
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Patient, VitalSign, Alert, Report
from app.schemas import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


def generate_vital_summary(vitals: list) -> dict:
    """Generate statistical summary of vital signs."""
    if not vitals:
        return {}

    def avg(field):
        values = [getattr(v, field) for v in vitals if getattr(v, field) is not None]
        return round(sum(values) / len(values), 2) if values else None

    def min_max(field):
        values = [getattr(v, field) for v in vitals if getattr(v, field) is not None]
        return (round(min(values), 2), round(max(values), 2)) if values else (None, None)

    hr_min, hr_max = min_max("heart_rate")
    bp_min, bp_max = min_max("blood_pressure_systolic")
    spo2_min, spo2_max = min_max("spo2")

    return {
        "heart_rate": {"avg": avg("heart_rate"), "min": hr_min, "max": hr_max},
        "blood_pressure_systolic": {"avg": avg("blood_pressure_systolic"), "min": bp_min, "max": bp_max},
        "blood_pressure_diastolic": {"avg": avg("blood_pressure_diastolic")},
        "respiratory_rate": {"avg": avg("respiratory_rate")},
        "spo2": {"avg": avg("spo2"), "min": spo2_min, "max": spo2_max},
        "temperature": {"avg": avg("temperature")},
        "gcs_score": {"avg": avg("gcs_score")},
        "data_points": len(vitals)
    }


def generate_report_content(
    patient: Patient,
    vital_summary: dict,
    risk_trend: list,
    alerts: list,
    report_type: str = "summary"
) -> tuple:
    """
    Generate AI-style clinical report content.
    Returns (content, recommendations)
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build report sections
    sections = []
    sections.append(f"ICU CLINICAL REPORT - {report_type.upper()}")
    sections.append(f"Generated: {current_time}")
    sections.append(f"Patient: {patient.name} (Bed {patient.bed_number})")
    sections.append(f"Age: {patient.age} | Gender: {patient.gender}")
    sections.append(f"Current Status: {patient.status.upper()} | Risk Score: {patient.risk_score:.2f}")
    sections.append("")

    # Vital signs summary
    sections.append("=" * 50)
    sections.append("VITAL SIGNS SUMMARY")
    sections.append("=" * 50)

    if vital_summary:
        hr = vital_summary.get("heart_rate", {})
        if hr.get("avg"):
            sections.append(f"Heart Rate: {hr['avg']} bpm (range: {hr.get('min', 'N/A')}-{hr.get('max', 'N/A')})")
            if hr["avg"] > 100:
                sections.append("  - NOTE: Tachycardia detected")
            elif hr["avg"] < 60:
                sections.append("  - NOTE: Bradycardia detected")

        bp = vital_summary.get("blood_pressure_systolic", {})
        if bp.get("avg"):
            sections.append(f"Blood Pressure: {bp['avg']}/{vital_summary.get('blood_pressure_diastolic', {}).get('avg', 'N/A')} mmHg")
            if bp["avg"] > 140:
                sections.append("  - NOTE: Hypertension detected")
            elif bp.get("min") and bp["min"] < 90:
                sections.append("  - NOTE: Hypotension episodes detected")

        spo2 = vital_summary.get("spo2", {})
        if spo2.get("avg"):
            sections.append(f"SpO2: {spo2['avg']}% (range: {spo2.get('min', 'N/A')}-{spo2.get('max', 'N/A')})")
            if spo2.get("min") and spo2["min"] < 92:
                sections.append("  - WARNING: Desaturation episodes detected")

        rr = vital_summary.get("respiratory_rate", {})
        if rr.get("avg"):
            sections.append(f"Respiratory Rate: {rr['avg']}/min")
            if rr["avg"] > 20:
                sections.append("  - NOTE: Tachypnea detected")

        temp = vital_summary.get("temperature", {})
        if temp.get("avg"):
            sections.append(f"Temperature: {temp['avg']}°C")
            if temp["avg"] > 38:
                sections.append("  - NOTE: Fever detected")
            elif temp["avg"] < 36:
                sections.append("  - NOTE: Hypothermia detected")

        gcs = vital_summary.get("gcs_score", {})
        if gcs.get("avg"):
            sections.append(f"GCS Score: {gcs['avg']}/15")
            if gcs["avg"] < 13:
                sections.append("  - WARNING: Reduced consciousness level")

    sections.append("")

    # Risk trend analysis
    sections.append("=" * 50)
    sections.append("RISK TREND ANALYSIS")
    sections.append("=" * 50)

    if risk_trend:
        recent_scores = [r["score"] for r in risk_trend[-12:]]  # Last 12 readings
        avg_recent = sum(recent_scores) / len(recent_scores) if recent_scores else 0
        trend = "IMPROVING" if len(recent_scores) >= 3 and recent_scores[-1] < recent_scores[0] else \
                "WORSENING" if len(recent_scores) >= 3 and recent_scores[-1] > recent_scores[0] else "STABLE"

        sections.append(f"Average Risk (last 12 readings): {avg_recent:.2f}")
        sections.append(f"Trend Direction: {trend}")
        sections.append(f"Current Level: {risk_trend[-1]['level'].upper() if risk_trend else 'N/A'}")

        if avg_recent > 0.7:
            sections.append("CRITICAL: Patient showing sustained high risk")
        elif avg_recent > 0.5:
            sections.append("HIGH: Close monitoring recommended")
        elif avg_recent > 0.3:
            sections.append("MODERATE: Standard monitoring sufficient")
        else:
            sections.append("LOW: Risk within normal parameters")
    else:
        sections.append("Insufficient data for trend analysis")

    sections.append("")

    # Alerts summary
    sections.append("=" * 50)
    sections.append("ALERT SUMMARY")
    sections.append("=" * 50)

    if alerts:
        critical_count = sum(1 for a in alerts if a.severity == "critical")
        high_count = sum(1 for a in alerts if a.severity == "high")
        sections.append(f"Total Alerts (24h): {len(alerts)}")
        sections.append(f"  Critical: {critical_count}")
        sections.append(f"  High: {high_count}")
        sections.append(f"  Medium/Low: {len(alerts) - critical_count - high_count}")

        # Most recent critical alerts
        critical_alerts = [a for a in alerts if a.severity in ("critical", "high")][:3]
        if critical_alerts:
            sections.append("")
            sections.append("Recent High-Priority Alerts:")
            for alert in critical_alerts:
                sections.append(f"  [{alert.severity.upper()}] {alert.message}")
    else:
        sections.append("No alerts in the last 24 hours")

    sections.append("")

    # AI Recommendations
    recommendations = []
    sections.append("=" * 50)
    sections.append("AI-GENERATED RECOMMENDATIONS")
    sections.append("=" * 50)

    if vital_summary:
        hr_avg = vital_summary.get("heart_rate", {}).get("avg")
        if hr_avg and hr_avg > 120:
            rec = "Consider cardiac workup: ECG, troponin levels"
            recommendations.append(rec)
            sections.append(f"- {rec}")

        spo2_avg = vital_summary.get("spo2", {}).get("avg")
        if spo2_avg and spo2_avg < 94:
            rec = "Evaluate respiratory status: consider ABG, chest imaging"
            recommendations.append(rec)
            sections.append(f"- {rec}")

        bp_avg = vital_summary.get("blood_pressure_systolic", {}).get("avg")
        if bp_avg and bp_avg < 90:
            rec = "Assess fluid status and consider vasopressor support"
            recommendations.append(rec)
            sections.append(f"- {rec}")

        temp_avg = vital_summary.get("temperature", {}).get("avg")
        if temp_avg and temp_avg > 38.5:
            rec = "Investigate infection source: blood cultures, procalcitonin"
            recommendations.append(rec)
            sections.append(f"- {rec}")

    if patient.risk_score > 0.7:
        rec = "INTENSIVE MONITORING: Consider ICU level care escalation"
        recommendations.append(rec)
        sections.append(f"- {rec}")
    elif patient.risk_score > 0.5:
        rec = "Enhanced monitoring with 15-minute vital checks"
        recommendations.append(rec)
        sections.append(f"- {rec}")

    if not recommendations:
        sections.append("- Continue standard monitoring protocols")
        sections.append("- Maintain current care plan")

    sections.append("")
    sections.append("=" * 50)
    sections.append(f"Report generated by AI Clinical Decision Support System")
    sections.append("This report is for clinical decision support only. Verify all data.")
    sections.append("=" * 50)

    return "\n".join(sections), "\n".join(recommendations)


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    request: ReportCreate,
    hours: int = Query(24, ge=1, le=72),
    db: Session = Depends(get_db)
):
    """Generate an AI clinical report for a patient."""
    patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    since = datetime.now() - timedelta(hours=hours)

    # Get vital signs
    vitals = db.query(VitalSign).filter(
        VitalSign.patient_id == request.patient_id,
        VitalSign.timestamp >= since
    ).order_by(VitalSign.timestamp).all()

    # Get alerts
    alerts = db.query(Alert).filter(
        Alert.patient_id == request.patient_id,
        Alert.timestamp >= since
    ).order_by(desc(Alert.timestamp)).all()

    # Generate summaries
    vital_summary = generate_vital_summary(vitals)

    risk_trend = [
        {"timestamp": v.timestamp.isoformat(), "score": v.risk_score, "level": v.risk_level}
        for v in vitals
    ]

    # Generate report content
    content, recommendations = generate_report_content(
        patient=patient,
        vital_summary=vital_summary,
        risk_trend=risk_trend,
        alerts=alerts,
        report_type=request.report_type
    )

    # Save report
    report = Report(
        patient_id=request.patient_id,
        report_type=request.report_type,
        content=content,
        vital_summary=vital_summary,
        risk_trend={"trend": risk_trend[-24:] if len(risk_trend) > 24 else risk_trend},
        recommendations=recommendations,
        generated_by="ai"
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return report


@router.get("/patient/{patient_id}", response_model=list[ReportResponse])
def get_patient_reports(
    patient_id: int,
    report_type: Optional[str] = Query(None, regex="^(summary|detailed|trend)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get reports for a specific patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    query = db.query(Report).filter(Report.patient_id == patient_id)
    if report_type:
        query = query.filter(Report.report_type == report_type)

    reports = query.order_by(desc(Report.generated_at)).limit(limit).all()
    return reports


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """Get a specific report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
