"""
Domain Event Handlers — React to events from the event bus.
This is the event-driven processing layer.
"""
from loguru import logger
from app.events.event_bus import InMemoryEventBus, EventType, DomainEvent


def register_handlers(bus: InMemoryEventBus):
    """Register all event handlers with the bus."""
    bus.subscribe(EventType.PATIENT_CREATED, on_patient_created)
    bus.subscribe(EventType.VITALS_RECORDED, on_vitals_recorded)
    bus.subscribe(EventType.DIAGNOSIS_ADDED, on_diagnosis_added)
    bus.subscribe(EventType.LAB_RESULT_UPDATED, on_lab_result_updated)
    bus.subscribe(EventType.AI_PREDICTION_MADE, on_ai_prediction_made)
    bus.subscribe(EventType.AI_ANOMALY_DETECTED, on_anomaly_detected)
    bus.subscribe(EventType.HUMAN_REVIEW_REQUIRED, on_human_review_required)
    bus.subscribe(EventType.ALERT_TRIGGERED, on_alert_triggered)
    logger.info("[EventBus] All handlers registered")


async def on_patient_created(event: DomainEvent):
    logger.info(f"[Handler] New patient registered: {event.payload.get('name')} ({event.payload.get('mrn')})")
    # In production: notify ward staff, initialize monitoring, create default alerts


async def on_vitals_recorded(event: DomainEvent):
    payload = event.payload
    patient_id = payload.get("patient_id")
    is_critical = payload.get("is_critical", False)

    if is_critical:
        logger.warning(f"[Handler] 🚨 CRITICAL VITALS for patient {patient_id} — escalating!")
        # In production: send push notification to attending doctor, trigger alarm
    else:
        logger.info(f"[Handler] Vitals recorded for patient {patient_id}")


async def on_diagnosis_added(event: DomainEvent):
    payload = event.payload
    logger.info(
        f"[Handler] Diagnosis added: {payload.get('condition')} "
        f"(severity: {payload.get('severity')}) for patient {payload.get('patient_id')}"
    )
    # In production: check drug interactions, trigger care pathway


async def on_lab_result_updated(event: DomainEvent):
    payload = event.payload
    if payload.get("is_critical"):
        logger.warning(f"[Handler] 🔬 CRITICAL LAB: {payload.get('test_name')} for patient {payload.get('patient_id')}")
    else:
        logger.info(f"[Handler] Lab result: {payload.get('test_name')} for patient {payload.get('patient_id')}")


async def on_ai_prediction_made(event: DomainEvent):
    payload = event.payload
    risk_level = payload.get("risk_level", "unknown")
    risk_score = payload.get("risk_score", 0)
    patient_id = payload.get("patient_id")

    if risk_level in ("critical", "moderate", "high"):
        logger.warning(
            f"[Handler] 🤖 AI HIGH RISK: Patient {patient_id} | "
            f"Level={risk_level.upper()} Score={risk_score:.2%}"
        )
        # In production: send SMS/push alert to doctor
    else:
        logger.info(f"[Handler] AI assessed patient {patient_id}: {risk_level} ({risk_score:.2%})")


async def on_anomaly_detected(event: DomainEvent):
    payload = event.payload
    logger.warning(
        f"[Handler] ⚠️ ANOMALY DETECTED for patient {event.aggregate_id} | "
        f"Score={payload.get('anomaly_score', 0):.2f} | "
        f"Anomalies: {len(payload.get('anomalies', []))}"
    )
    # In production: trigger real-time alert to dashboard via WebSocket


async def on_human_review_required(event: DomainEvent):
    payload = event.payload
    logger.info(
        f"[Handler] 👨‍⚕️ Human review required: Prediction {event.aggregate_id} | "
        f"Patient {payload.get('patient_id')} | Confidence={payload.get('confidence', 0):.0%}"
    )
    # In production: add to doctor's review queue, send notification


async def on_alert_triggered(event: DomainEvent):
    payload = event.payload
    logger.info(f"[Handler] 🔔 Alert: {payload.get('title')} for patient {payload.get('patient_id')}")
