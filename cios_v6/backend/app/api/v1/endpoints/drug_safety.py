from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.drug_safety import (
    full_drug_safety_check,
    check_drug_interactions,
    check_allergy_crossmatch,
    DrugSafetyReport,
)
from app.models.models import Patient

router = APIRouter(prefix="/drug-safety", tags=["Drug Safety"])


class DrugCheckRequest(BaseModel):
    drug_name: str
    patient_id: int
    existing_medications: Optional[List[str]] = None
    patient_allergies: Optional[List[str]] = None


@router.post("/check")
async def check_drug_safety(
    body: DrugCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.PRESCRIPTION_WRITE)),
):
    result = await db.execute(
        __import__("sqlalchemy").select(Patient).where(Patient.id == body.patient_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = body.existing_medications or (patient.current_medications or [])
    allergies = body.patient_allergies or (patient.allergies or [])

    report = full_drug_safety_check(body.drug_name, existing, allergies)

    return {
        "drug_name": report.drug_name,
        "drug_class": report.drug_class,
        "is_safe": report.is_safe,
        "summary": report.summary,
        "interactions": [
            {
                "drug_a": i.drug_a,
                "drug_b": i.drug_b,
                "severity": i.severity,
                "description": i.description,
                "recommendation": i.recommendation,
            }
            for i in report.interactions
        ],
        "allergies": [
            {
                "drug": a.drug,
                "allergen": a.allergen,
                "reaction_type": a.reaction_type,
                "severity": a.severity,
                "description": a.description,
            }
            for a in report.allergies
        ],
        "duplicates": report.duplicates,
    }
