from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.messaging_service import MessagingService
from app.events.event_bus import publish_event, EventType

router = APIRouter(prefix="/messaging", tags=["Messaging"])


class CreateConversationRequest(BaseModel):
    subject: str
    participant_ids: List[int]
    patient_id: Optional[int] = None
    is_urgent: bool = False
    opening_message: Optional[str] = None


class SendMessageRequest(BaseModel):
    body: str
    message_type: str = "text"


# ── Conversations ─────────────────────────────────────────

@router.post("/conversations", status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not body.participant_ids:
        raise HTTPException(status_code=400, detail="At least one participant required")

    conv = await MessagingService.create_conversation(
        db,
        creator_id      = current_user.id,
        subject         = body.subject,
        participant_ids = body.participant_ids,
        patient_id      = body.patient_id,
        is_urgent       = body.is_urgent,
        opening_message = body.opening_message,
    )
    return {"message": "Conversation created", "conversation_id": conv.id,
            "subject": conv.subject}


@router.get("/conversations")
async def list_conversations(
    unread_only: bool = False,
    skip:  int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    convs = await MessagingService.get_user_conversations(
        db, current_user.id, skip, limit, unread_only
    )
    return {"total": len(convs), "conversations": convs}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: int,
    skip:  int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    messages = await MessagingService.get_conversation_messages(
        db, conv_id, current_user.id, skip, limit
    )
    if messages is None:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")
    return {"conversation_id": conv_id, "messages": messages, "count": len(messages)}


@router.post("/conversations/{conv_id}/messages", status_code=201)
async def send_message(
    conv_id: int,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not body.body.strip():
        raise HTTPException(status_code=400, detail="Message body cannot be empty")

    msg = await MessagingService.send_message(
        db, conv_id, current_user.id, body.body.strip(), body.message_type
    )
    await publish_event(
        EventType.ALERT_TRIGGERED,
        aggregate_type="Message",
        aggregate_id=str(msg.id),
        payload={"conversation_id": conv_id, "sender_id": current_user.id,
                 "sender_name": current_user.full_name}
    )
    return {
        "message_id": msg.id,
        "conversation_id": conv_id,
        "body": msg.body,
        "sender": current_user.full_name,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    count = await MessagingService.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.get("/users")
async def get_messageable_users(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All staff that can be messaged."""
    users = await MessagingService.get_all_users_for_messaging(db, current_user.id)
    return {"users": users}
