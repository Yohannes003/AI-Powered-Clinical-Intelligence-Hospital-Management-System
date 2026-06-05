"""
HL7 FHIR R4 API Layer — provides standards-based interoperability for EMR integration.
Resources: Patient, Observation (vitals/labs), Condition (diagnoses), MedicationRequest.
Conforms to the FHIR R4 (4.0.1) specification for read/search operations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.models import Patient, VitalSign, Diagnosis, LabResult

router = APIRouter(prefix="/fhir", tags=["FHIR R4"])


def _build_fhir_patient(p) -> dict:
    name_parts = (p.full_name or "").split(" ", 1)
    dob = p.date_of_birth.isoformat() if p.date_of_birth else None
    return {
        "resourceType": "Patient",
        "id": str(p.id),
        "identifier": [
            {
                "system": "http://cios.hospital/mrn",
                "value": p.patient_id,
            }
        ],
        "active": p.status not in ("discharged", "deceased"),
        "name": [
            {
                "use": "official",
                "family": name_parts[1] if len(name_parts) > 1 else "",
                "given": [name_parts[0]] if name_parts else [],
            }
        ],
        "gender": p.gender.lower() if p.gender else "unknown",
        "birthDate": dob.split("T")[0] if dob else None,
        "deceasedBoolean": p.status == "deceased",
        "address": [
            {
                "text": p.address,
            }
        ] if p.address else [],
        "telecom": [
            {"system": "phone", "value": p.contact_phone},
            {"system": "email", "value": p.contact_email},
        ] if p.contact_phone or p.contact_email else [],
        "generalPractitioner": [
            {"reference": f"Practitioner/{p.attending_doctor_id}"}
        ] if p.attending_doctor_id else [],
        "meta": {
            "lastUpdated": p.updated_at.isoformat() if p.updated_at else p.created_at.isoformat() if p.created_at else None,
        },
    }


def _build_fhir_observation(v, patient_id: int) -> list:
    obs = []
    mapping = [
        ("temperature", "8867-4", "Body temperature", "°C", "urn:oid:2.16.840.1.113883.6.1"),
        ("heart_rate", "8867-4", "Heart rate", "bpm", "urn:oid:2.16.840.1.113883.6.1"),
        ("systolic_bp", "8480-6", "Systolic blood pressure", "mmHg", "urn:oid:2.16.840.1.113883.6.1"),
        ("diastolic_bp", "8462-4", "Diastolic blood pressure", "mmHg", "urn:oid:2.16.840.1.113883.6.1"),
        ("respiratory_rate", "9279-1", "Respiratory rate", "breaths/min", "urn:oid:2.16.840.1.113883.6.1"),
        ("oxygen_saturation", "2708-6", "Oxygen saturation", "%", "urn:oid:2.16.840.1.113883.6.1"),
        ("blood_glucose", "2345-7", "Glucose", "mg/dL", "urn:oid:2.16.840.1.113883.6.1"),
    ]
    recorded = v.recorded_at.isoformat() if v.recorded_at else None
    for field, loinc, display, unit, system in mapping:
        val = getattr(v, field, None)
        if val is not None:
            obs.append({
                "resourceType": "Observation",
                "id": f"vital-{v.id}-{field}",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs",
                    }]
                }],
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": loinc,
                        "display": display,
                    }],
                    "text": display,
                },
                "subject": {
                    "reference": f"Patient/{patient_id}",
                },
                "effectiveDateTime": recorded,
                "issued": recorded,
                "valueQuantity": {
                    "value": val,
                    "unit": unit,
                    "system": system,
                },
                "meta": {"lastUpdated": recorded},
            })
    return obs


@router.get("/Patient/{patient_id}")
async def fhir_read_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        pid = int(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient ID")
    result = await db.execute(select(Patient).where(Patient.id == pid))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _build_fhir_patient(patient)


@router.get("/Patient")
async def fhir_search_patient(
    _id: Optional[str] = Query(None, alias="_id"),
    identifier: Optional[str] = Query(None),
    family: Optional[str] = Query(None),
    given: Optional[str] = Query(None),
    birthdate: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(Patient)

    if _id:
        try:
            query = query.where(Patient.id == int(_id))
        except ValueError:
            pass
    if identifier:
        query = query.where(Patient.patient_id.ilike(f"%{identifier}%"))
    if family:
        query = query.where(Patient.full_name.ilike(f"%{family}%"))
    if given:
        query = query.where(Patient.full_name.ilike(f"%{given}%"))
    if gender:
        query = query.where(Patient.gender.ilike(gender))
    if birthdate:
        try:
            bd = datetime.fromisoformat(birthdate)
            query = query.where(Patient.date_of_birth.cast(str).like(f"{bd.date()}%"))
        except ValueError:
            pass

    result = await db.execute(query.order_by(Patient.created_at.desc()).limit(50))
    patients = result.scalars().all()

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(patients),
        "entry": [
            {
                "fullUrl": f"/api/v1/fhir/Patient/{p.id}",
                "resource": _build_fhir_patient(p),
            }
            for p in patients
        ],
    }


@router.get("/Observation")
async def fhir_search_observation(
    patient: Optional[str] = Query(None, alias="patient"),
    code: Optional[str] = Query(None),
    _count: int = Query(50, alias="_count", le=200),
    _sort: Optional[str] = Query(None, alias="_sort"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not patient:
        raise HTTPException(status_code=400, detail="patient parameter is required")

    try:
        pid = patient.replace("Patient/", "").replace("patient/", "")
        pid = int(pid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient reference")

    result = await db.execute(
        select(VitalSign)
        .where(VitalSign.patient_id == pid)
        .order_by(VitalSign.recorded_at.desc())
        .limit(_count)
    )
    vitals = result.scalars().all()

    entries = []
    for v in vitals:
        observations = _build_fhir_observation(v, pid)
        loinc_map = {
            "8867-4": "temperature",
            "8480-6": "systolic_bp",
            "8462-4": "diastolic_bp",
            "9279-1": "respiratory_rate",
            "2708-6": "oxygen_saturation",
            "2345-7": "blood_glucose",
        }
        if code:
            field = loinc_map.get(code)
            if field:
                observations = [o for o in observations if o["code"]["coding"][0]["code"] == code]
            else:
                observations = []
        entries.extend([
            {
                "fullUrl": f"/api/v1/fhir/Observation/{o['id']}",
                "resource": o,
            }
            for o in observations
        ])

    if _sort == "-date":
        entries.sort(key=lambda e: e["resource"].get("effectiveDateTime", ""), reverse=True)

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries,
    }


@router.get("/Condition")
async def fhir_search_condition(
    patient: Optional[str] = Query(None, alias="patient"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not patient:
        raise HTTPException(status_code=400, detail="patient parameter is required")
    try:
        pid = int(patient.replace("Patient/", "").replace("patient/", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient reference")

    result = await db.execute(
        select(Diagnosis)
        .where(Diagnosis.patient_id == pid)
        .order_by(Diagnosis.diagnosed_at.desc())
    )
    diagnoses = result.scalars().all()

    entries = []
    for d in diagnoses:
        entry = {
            "resourceType": "Condition",
            "id": f"condition-{d.id}",
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "resolved" if d.resolved_at else "active",
                }]
            },
            "severity": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": {
                        "mild": "255604002",
                        "moderate": "6736007",
                        "severe": "24484000",
                        "critical": "442452003",
                    }.get(d.severity, "6736007"),
                    "display": d.severity.capitalize() if d.severity else "Moderate",
                }]
            } if d.severity else None,
            "code": {
                "coding": [{
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "code": d.icd_code,
                    "display": d.condition_name,
                }] if d.icd_code else [],
                "text": d.condition_name,
            },
            "subject": {"reference": f"Patient/{pid}"},
            "recordedDate": d.diagnosed_at.isoformat() if d.diagnosed_at else None,
            "note": [{"text": d.description}] if d.description else [],
        }
        entries.append({
            "fullUrl": f"/api/v1/fhir/Condition/{d.id}",
            "resource": entry,
        })

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries,
    }


@router.get("/metadata")
async def fhir_capabilities():
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": datetime.utcnow().isoformat(),
        "publisher": "CIOS — Clinical Intelligence Operating System",
        "kind": "instance",
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "resource": [
                {
                    "type": "Patient",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "_id", "type": "token"},
                        {"name": "identifier", "type": "token"},
                        {"name": "family", "type": "string"},
                        {"name": "given", "type": "string"},
                        {"name": "birthdate", "type": "date"},
                        {"name": "gender", "type": "token"},
                    ],
                },
                {
                    "type": "Observation",
                    "interaction": [{"code": "search-type"}],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                        {"name": "code", "type": "token"},
                        {"name": "_sort", "type": "string"},
                    ],
                },
                {
                    "type": "Condition",
                    "interaction": [{"code": "search-type"}],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                    ],
                },
            ],
        }],
    }
