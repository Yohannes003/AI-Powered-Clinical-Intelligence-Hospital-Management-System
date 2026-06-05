"""
Event Bus — Kafka-ready abstraction layer.

Currently uses Redis Pub/Sub + in-memory for development.
To switch to Kafka: implement KafkaEventBus with same interface.
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict, field
from loguru import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class EventType(str, Enum):
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    PATIENT_ADMITTED = "patient_admitted"
    PATIENT_DISCHARGED = "patient_discharged"
    DIAGNOSIS_ADDED = "diagnosis_added"
    LAB_RESULT_UPDATED = "lab_result_updated"
    VITALS_RECORDED = "vitals_recorded"
    AI_PREDICTION_MADE = "ai_prediction_made"
    AI_ANOMALY_DETECTED = "ai_anomaly_detected"
    TREATMENT_STARTED = "treatment_started"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    REPORT_GENERATED = "report_generated"
    DIGITAL_TWIN_UPDATED = "digital_twin_updated"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    AI_PIPELINE_COMPLETED = "ai_pipeline_completed"


@dataclass
class DomainEvent:
    event_type: EventType
    aggregate_type: str
    aggregate_id: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class InMemoryEventBus:
    """Development event bus — stores all events in memory + processes handlers."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_store: List[DomainEvent] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: EventType, handler: Callable):
        key = event_type.value
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
        logger.info(f"[EventBus] Subscribed {handler.__name__} to {key}")

    async def publish(self, event: DomainEvent):
        self._event_store.append(event)
        await self._queue.put(event)
        logger.info(f"[EventBus] Published {event.event_type.value} | aggregate={event.aggregate_id}")

    async def start(self):
        self._running = True
        asyncio.create_task(self._process_loop())
        logger.info("[EventBus] Started in-memory event processor")

    async def _process_loop(self):
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[EventBus] Error processing event: {e}")

    async def _dispatch(self, event: DomainEvent):
        handlers = self._handlers.get(event.event_type.value, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[EventBus] Handler {handler.__name__} failed: {e}")

    def get_events(self, aggregate_id: Optional[str] = None,
                   event_type: Optional[EventType] = None) -> List[DomainEvent]:
        events = self._event_store
        if aggregate_id:
            events = [e for e in events if e.aggregate_id == aggregate_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    async def stop(self):
        self._running = False


class RedisEventBus(InMemoryEventBus):
    """Production-ready Redis Pub/Sub event bus."""

    def __init__(self, redis_url: str):
        super().__init__()
        self._redis_url = redis_url
        self._redis = None
        self._pubsub = None

    async def start(self):
        if REDIS_AVAILABLE:
            self._redis = await aioredis.from_url(self._redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            logger.info("[EventBus] Connected to Redis")
        await super().start()

    async def publish(self, event: DomainEvent):
        await super().publish(event)
        if self._redis:
            try:
                channel = f"cios:events:{event.event_type.value}"
                await self._redis.publish(channel, event.to_json())
                # Also append to stream for durability
                await self._redis.xadd(
                    "cios:event_stream",
                    {"event": event.to_json()},
                    maxlen=10000
                )
            except Exception as e:
                logger.warning(f"[EventBus] Redis publish failed (using in-memory): {e}")


# ─── Global Event Bus Singleton ──────────────────────────
_event_bus: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    global _event_bus
    if _event_bus is None:
        from app.core.config import settings
        _event_bus = RedisEventBus(settings.REDIS_URL)
    return _event_bus


async def publish_event(
    event_type: EventType,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    metadata: dict = None,
    correlation_id: str = None
):
    """Convenience wrapper to publish events."""
    bus = get_event_bus()
    event = DomainEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        metadata=metadata or {},
        correlation_id=correlation_id
    )
    await bus.publish(event)
    return event
