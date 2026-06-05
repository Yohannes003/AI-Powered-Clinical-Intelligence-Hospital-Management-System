from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, patients, clinical, ai, reports, admin, messaging,
    referrals, icu, fhir, drug_safety, orders, note_templates,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(clinical.router)
api_router.include_router(ai.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(messaging.router)
api_router.include_router(referrals.router)
api_router.include_router(icu.router)
api_router.include_router(fhir.router)
api_router.include_router(drug_safety.router)
api_router.include_router(orders.router)
api_router.include_router(note_templates.router)
