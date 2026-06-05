from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.models import Patient, ClinicalNote

router = APIRouter(prefix="/notes", tags=["Clinical Notes"])


class NoteType(str, Enum):
    SOAP = "soap"
    HP = "history_and_physical"
    PROGRESS = "progress_note"
    DISCHARGE = "discharge_summary"
    CONSULT = "consultation"


SOAP_TEMPLATE = {
    "note_type": "SOAP Note",
    "sections": [
        {"name": "subjective", "label": "Subjective", "fields": [
            {"key": "chief_complaint", "label": "Chief Complaint", "type": "text"},
            {"key": "history_of_present_illness", "label": "History of Present Illness", "type": "textarea"},
            {"key": "pain_level", "label": "Pain Level (0-10)", "type": "number"},
            {"key": "symptoms", "label": "Symptoms", "type": "list"},
        ]},
        {"name": "objective", "label": "Objective", "fields": [
            {"key": "vitals_summary", "label": "Vital Signs Summary", "type": "textarea"},
            {"key": "physical_exam", "label": "Physical Exam Findings", "type": "textarea"},
            {"key": "relevant_labs", "label": "Relevant Labs/Imaging", "type": "textarea"},
        ]},
        {"name": "assessment", "label": "Assessment", "fields": [
            {"key": "diagnosis", "label": "Diagnosis", "type": "text"},
            {"key": "differential", "label": "Differential Diagnosis", "type": "textarea"},
            {"key": "clinical_impression", "label": "Clinical Impression", "type": "textarea"},
        ]},
        {"name": "plan", "label": "Plan", "fields": [
            {"key": "medications", "label": "Medication Changes", "type": "textarea"},
            {"key": "tests_ordered", "label": "Tests/Imaging Ordered", "type": "textarea"},
            {"key": "follow_up", "label": "Follow-up Plan", "type": "textarea"},
            {"key": "patient_education", "label": "Patient Education", "type": "textarea"},
        ]},
    ],
}

HP_TEMPLATE = {
    "note_type": "History & Physical",
    "sections": [
        {"name": "history", "label": "History", "fields": [
            {"key": "chief_complaint", "label": "Chief Complaint", "type": "text"},
            {"key": "hpi", "label": "History of Present Illness", "type": "textarea"},
            {"key": "pmh", "label": "Past Medical History", "type": "textarea"},
            {"key": "psh", "label": "Past Surgical History", "type": "textarea"},
            {"key": "medications", "label": "Current Medications", "type": "list"},
            {"key": "allergies", "label": "Allergies", "type": "list"},
            {"key": "social_history", "label": "Social History", "type": "textarea"},
            {"key": "family_history", "label": "Family History", "type": "textarea"},
        ]},
        {"name": "physical_exam", "label": "Physical Examination", "fields": [
            {"key": "vitals", "label": "Vital Signs", "type": "textarea"},
            {"key": "general", "label": "General Appearance", "type": "textarea"},
            {"key": "heent", "label": "HEENT", "type": "textarea"},
            {"key": "cardiovascular", "label": "Cardiovascular", "type": "textarea"},
            {"key": "respiratory", "label": "Respiratory", "type": "textarea"},
            {"key": "abdominal", "label": "Abdominal", "type": "textarea"},
            {"key": "neurological", "label": "Neurological", "type": "textarea"},
            {"key": "musculoskeletal", "label": "Musculoskeletal", "type": "textarea"},
        ]},
        {"name": "assessment_plan", "label": "Assessment & Plan", "fields": [
            {"key": "assessment", "label": "Assessment", "type": "textarea"},
            {"key": "plan", "label": "Plan", "type": "textarea"},
        ]},
    ],
}

PROGRESS_TEMPLATE = {
    "note_type": "Progress Note",
    "sections": [
        {"name": "subjective", "label": "Subjective Update", "fields": [
            {"key": "interval_history", "label": "Interval History", "type": "textarea"},
            {"key": "pain_level", "label": "Pain Level", "type": "number"},
            {"key": "new_symptoms", "label": "New Symptoms", "type": "textarea"},
        ]},
        {"name": "objective", "label": "Objective Update", "fields": [
            {"key": "vitals_today", "label": "Today's Vital Signs", "type": "textarea"},
            {"key": "exam_findings", "label": "Exam Findings", "type": "textarea"},
            {"key": "labs_reviewed", "label": "Labs Reviewed", "type": "textarea"},
        ]},
        {"name": "assessment", "label": "Assessment Update", "fields": [
            {"key": "change_in_status", "label": "Change in Status", "type": "textarea"},
            {"key": "problems", "label": "Active Problem List", "type": "list"},
        ]},
        {"name": "plan", "label": "Plan for Today", "fields": [
            {"key": "today_plan", "label": "Today's Plan", "type": "textarea"},
            {"key": "disposition", "label": "Disposition", "type": "text"},
        ]},
    ],
}

DISCHARGE_TEMPLATE = {
    "note_type": "Discharge Summary",
    "sections": [
        {"name": "admission_info", "label": "Admission Information", "fields": [
            {"key": "admission_date", "label": "Admission Date", "type": "date"},
            {"key": "discharge_date", "label": "Discharge Date", "type": "date"},
            {"key": "admitting_diagnosis", "label": "Admitting Diagnosis", "type": "text"},
            {"key": "discharge_diagnosis", "label": "Discharge Diagnosis", "type": "text"},
        ]},
        {"name": "hospital_course", "label": "Hospital Course", "fields": [
            {"key": "summary", "label": "Summary of Hospital Course", "type": "textarea"},
            {"key": "significant_procedures", "label": "Significant Procedures", "type": "textarea"},
            {"key": "complications", "label": "Complications", "type": "textarea"},
        ]},
        {"name": "discharge_plan", "label": "Discharge Plan", "fields": [
            {"key": "medications_at_discharge", "label": "Medications at Discharge", "type": "list"},
            {"key": "medication_changes", "label": "Medication Changes & Rationale", "type": "textarea"},
            {"key": "follow_up_appointments", "label": "Follow-up Appointments", "type": "textarea"},
            {"key": "pending_results", "label": "Pending Labs/Results to Follow", "type": "textarea"},
            {"key": "activity_restrictions", "label": "Activity/Diet Restrictions", "type": "textarea"},
            {"key": "when_to_seek_care", "label": "When to Seek Medical Attention", "type": "textarea"},
        ]},
        {"name": "medication_reconciliation", "label": "Medication Reconciliation", "fields": [
            {"key": "home_meds_resumed", "label": "Home Medications Resumed", "type": "textarea"},
            {"key": "new_meds_started", "label": "New Medications Started", "type": "textarea"},
            {"key": "meds_discontinued", "label": "Medications Discontinued", "type": "textarea"},
        ]},
    ],
}

NOTE_TEMPLATES = {
    "soap": SOAP_TEMPLATE,
    "history_and_physical": HP_TEMPLATE,
    "progress_note": PROGRESS_TEMPLATE,
    "discharge_summary": DISCHARGE_TEMPLATE,
}


class ClinicalNoteCreate(BaseModel):
    patient_id: int
    note_type: NoteType
    content: dict


@router.get("/templates")
async def list_templates():
    return {
        "templates": [
            {"id": key, "name": tmpl["note_type"], "sections": tmpl["sections"]}
            for key, tmpl in NOTE_TEMPLATES.items()
        ]
    }


@router.get("/templates/{note_type}")
async def get_template(note_type: str):
    tmpl = NOTE_TEMPLATES.get(note_type)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template '{note_type}' not found")
    return tmpl


@router.post("/", status_code=201)
async def create_note(
    body: ClinicalNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tmpl = NOTE_TEMPLATES.get(body.note_type.value)
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown note type: {body.note_type}")

    note = ClinicalNote(
        patient_id=body.patient_id,
        author_id=current_user.id,
        note_type=body.note_type.value,
        content=body.content,
    )
    db.add(note)
    await db.flush()

    return {"note_id": note.id, "note_type": body.note_type.value, "message": "Note saved"}
