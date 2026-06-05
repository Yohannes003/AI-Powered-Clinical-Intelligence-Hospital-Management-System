from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.ai_service import AIService
from app.models.models import AIPrediction, ClinicalDigitalTwin, GroundTruthRecord
from app.ai_engine.pipeline import ClinicalAIPipeline

router = APIRouter(prefix="/ai", tags=["AI Engine"])


class ReviewSubmit(BaseModel):
    review_notes: str


@router.post("/assess/{patient_id}")
async def run_assessment(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Run full AI clinical assessment for a patient."""
    try:
        pid = int(patient_id) if patient_id.isdigit() else patient_id
        result = await AIService.run_full_assessment(db, pid, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assessment failed: {str(e)}")


@router.get("/predictions/{patient_id}")
async def get_predictions(
    patient_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pid = int(patient_id) if patient_id.isdigit() else patient_id
    predictions = await AIService.get_patient_predictions(db, pid, limit)
    return {
        "patient_id": patient_id,
        "predictions": [
            {c.name: getattr(p, c.name) for c in p.__table__.columns}
            for p in predictions
        ]
    }


@router.get("/digital-twin/{patient_id}")
async def get_digital_twin(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pid = int(patient_id) if patient_id.isdigit() else patient_id
    result = await db.execute(
        select(ClinicalDigitalTwin).where(ClinicalDigitalTwin.patient_id == pid)
    )
    twin = result.scalar_one_or_none()
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin not yet initialized. Run AI assessment first.")
    return {c.name: getattr(twin, c.name) for c in twin.__table__.columns}


@router.get("/pending-reviews")
async def get_pending_reviews(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    predictions = await AIService.get_pending_reviews(db, limit)
    return {
        "count": len(predictions),
        "pending": [
            {c.name: getattr(p, c.name) for c in p.__table__.columns}
            for p in predictions
        ]
    }


@router.post("/review/{prediction_id}")
async def submit_review(
    prediction_id: int,
    body: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    prediction = await AIService.submit_review(db, prediction_id, current_user.id, body.review_notes)
    return {
        "message": "Review submitted",
        "prediction_id": prediction.id,
        "reviewed_at": prediction.reviewed_at.isoformat()
    }


# ─── 3-Stage AI Pipeline ──────────────────────────────────

@router.post("/pipeline/{patient_id}")
async def run_ai_pipeline(
    patient_id,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Run the 3-stage AI pipeline: AI/ML → LLM → GenAI Ground Truth."""
    try:
        result = await ClinicalAIPipeline.run_pipeline(db, patient_id, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI pipeline failed: {str(e)}")


@router.get("/pipeline-results/{patient_id}")
async def get_pipeline_results(
    patient_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pid = int(patient_id) if patient_id.isdigit() else patient_id
    records = await ClinicalAIPipeline.get_pipeline_results(db, pid, limit)
    return {
        "patient_id": patient_id,
        "results": [
            {
                c.name: getattr(r, c.name) for c in r.__table__.columns
            }
            for r in records
        ]
    }
