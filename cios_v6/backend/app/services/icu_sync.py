import asyncio
from loguru import logger
from sqlalchemy import text, select
from app.db.session import safe_get_icu_db, AsyncSessionLocal
from app.models.models import Patient


async def _sync_once():
    icu_db = await safe_get_icu_db()
    if icu_db is None:
        logger.debug("ICU DB not configured — skipping sync")
        return

    async with AsyncSessionLocal() as db:
        try:
            q = text("SELECT id, name, gender, admission_date, bed_number, status, date_of_birth FROM patients")
            try:
                result = await icu_db.execute(q)
                rows = result.fetchall()
            except Exception:
                rows = []

            for r in rows:
                icu_id = getattr(r, "id", None)
                if icu_id is None:
                    continue
                mrn = f"ICU-{icu_id}"
                existing = await db.execute(select(Patient).where(Patient.patient_id == mrn))
                patient = existing.scalar_one_or_none()
                dob = getattr(r, "date_of_birth", None)
                from datetime import datetime as _dt
                placeholder_dob = _dt(1900, 1, 1)

                if patient:
                    updated = False
                    if getattr(patient, "full_name", None) != getattr(r, "name", None):
                        patient.full_name = getattr(r, "name", patient.full_name)
                        updated = True
                    if getattr(patient, "gender", None) != getattr(r, "gender", None):
                        patient.gender = getattr(r, "gender", patient.gender)
                        updated = True
                    if getattr(patient, "admission_date", None) != getattr(r, "admission_date", None):
                        patient.admission_date = getattr(r, "admission_date", patient.admission_date)
                        updated = True
                    if getattr(patient, "status", None) != "icu":
                        patient.status = "icu"
                        updated = True
                    if updated:
                        db.add(patient)
                else:
                    patient = Patient(
                        patient_id=mrn,
                        full_name=getattr(r, "name", f"ICU Patient {icu_id}"),
                        date_of_birth=dob or placeholder_dob,
                        gender=getattr(r, "gender", "Other") or "Other",
                        status="icu",
                        admission_date=getattr(r, "admission_date", None),
                    )
                    db.add(patient)

            await db.flush()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.exception("Error while syncing ICU patients: {}", e)
        finally:
            await icu_db.close()


async def start_icu_sync(stop_event: asyncio.Event, interval_seconds: int = 300):
    logger.info("Starting ICU sync task (interval={}s)", interval_seconds)
    try:
        while not stop_event.is_set():
            try:
                await _sync_once()
            except Exception:
                logger.exception("Unhandled error during ICU sync run")
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
    except asyncio.TimeoutError:
        # timeout means continue loop
        pass
    except Exception:
        logger.exception("ICU sync task terminated unexpectedly")
    logger.info("ICU sync task stopped")
