"""
Messaging Service — secure clinical communication.
Handles conversations, participants, messages, unread counts, receipts.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List, Optional
from datetime import datetime

from app.models.models import (
    Conversation, ConversationParticipant, Message,
    MessageReceipt, ConversationStatus, User
)


class MessagingService:

    # ── Conversations ─────────────────────────────────────

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        creator_id: int,
        subject: str,
        participant_ids: List[int],
        patient_id: Optional[int] = None,
        is_urgent: bool = False,
        opening_message: Optional[str] = None,
    ) -> Conversation:
        conv = Conversation(
            subject=subject,
            patient_id=patient_id,
            created_by_id=creator_id,
            is_urgent=is_urgent,
        )
        db.add(conv)
        await db.flush()

        # Add all participants (including creator)
        all_ids = list(set([creator_id] + participant_ids))
        for uid in all_ids:
            db.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))

        # Add opening message
        if opening_message:
            msg = Message(
                conversation_id=conv.id,
                sender_id=creator_id,
                body=opening_message,
            )
            db.add(msg)

        await db.flush()
        return conv

    @staticmethod
    async def get_user_conversations(
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 30,
        unread_only: bool = False,
    ) -> List[dict]:
        """Return conversations for a user with unread counts."""
        # Get conversations where user is a participant
        part_q = (
            select(ConversationParticipant.conversation_id,
                   ConversationParticipant.last_read_at)
            .where(ConversationParticipant.user_id == user_id)
        )
        part_result = await db.execute(part_q)
        parts = {r.conversation_id: r.last_read_at for r in part_result}

        if not parts:
            return []

        conv_q = (
            select(Conversation)
            .where(Conversation.id.in_(list(parts.keys())))
            .where(Conversation.status != ConversationStatus.CLOSED)
            .order_by(desc(Conversation.updated_at))
            .offset(skip).limit(limit)
        )
        conv_result = await db.execute(conv_q)
        convs = conv_result.scalars().all()

        result = []
        for conv in convs:
            last_read = parts.get(conv.id)

            # Count unread messages
            unread_q = select(func.count(Message.id)).where(
                Message.conversation_id == conv.id,
                Message.sender_id != user_id,
            )
            if last_read:
                unread_q = unread_q.where(Message.created_at > last_read)
            unread_count = (await db.execute(unread_q)).scalar()

            if unread_only and unread_count == 0:
                continue

            # Last message preview
            last_msg_q = (
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(desc(Message.created_at)).limit(1)
            )
            last_msg = (await db.execute(last_msg_q)).scalar_one_or_none()

            # Participants
            p_q = (
                select(ConversationParticipant, User)
                .join(User, ConversationParticipant.user_id == User.id)
                .where(ConversationParticipant.conversation_id == conv.id)
            )
            p_result = await db.execute(p_q)
            participants = [
                {"id": row.User.id, "name": row.User.full_name,
                 "role": row.User.role, "email": row.User.email}
                for row in p_result
            ]

            result.append({
                "id": conv.id,
                "subject": conv.subject,
                "patient_id": conv.patient_id,
                "is_urgent": conv.is_urgent,
                "status": conv.status,
                "unread_count": unread_count or 0,
                "created_by_id": conv.created_by_id,
                "participants": participants,
                "last_message": {
                    "body": last_msg.body[:80] + "..." if last_msg and len(last_msg.body) > 80 else (last_msg.body if last_msg else ""),
                    "sender_id": last_msg.sender_id if last_msg else None,
                    "created_at": last_msg.created_at.isoformat() if last_msg else None,
                } if last_msg else None,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            })

        return result

    @staticmethod
    async def get_conversation_messages(
        db: AsyncSession,
        conversation_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        """Get messages for a conversation and mark as read."""
        # Verify participant
        part_q = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
        part = (await db.execute(part_q)).scalar_one_or_none()
        if not part:
            return []

        # Get messages
        msg_q = (
            select(Message, User)
            .join(User, Message.sender_id == User.id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .offset(skip).limit(limit)
        )
        msg_result = await db.execute(msg_q)

        messages = []
        for row in msg_result:
            msg = row.Message
            sender = row.User

            # Add read receipt if not already there
            receipt_q = select(MessageReceipt).where(
                MessageReceipt.message_id == msg.id,
                MessageReceipt.user_id == user_id,
            )
            existing = (await db.execute(receipt_q)).scalar_one_or_none()
            if not existing and msg.sender_id != user_id:
                db.add(MessageReceipt(message_id=msg.id, user_id=user_id))

            messages.append({
                "id": msg.id,
                "body": msg.body,
                "message_type": msg.message_type,
                "sender": {
                    "id": sender.id,
                    "name": sender.full_name,
                    "role": sender.role,
                },
                "is_edited": msg.is_edited,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        # Mark last_read_at
        part.last_read_at = datetime.utcnow()
        await db.flush()
        return messages

    @staticmethod
    async def send_message(
        db: AsyncSession,
        conversation_id: int,
        sender_id: int,
        body: str,
        message_type: str = "text",
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            body=body,
            message_type=message_type,
        )
        db.add(msg)

        # Bump conversation updated_at for ordering
        conv_q = select(Conversation).where(Conversation.id == conversation_id)
        conv = (await db.execute(conv_q)).scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.utcnow()

        await db.flush()
        return msg

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: int) -> int:
        """Total unread messages across all conversations."""
        part_q = (
            select(ConversationParticipant)
            .where(ConversationParticipant.user_id == user_id)
        )
        parts = (await db.execute(part_q)).scalars().all()

        total = 0
        for part in parts:
            q = select(func.count(Message.id)).where(
                Message.conversation_id == part.conversation_id,
                Message.sender_id != user_id,
            )
            if part.last_read_at:
                q = q.where(Message.created_at > part.last_read_at)
            count = (await db.execute(q)).scalar()
            total += count or 0
        return total

    @staticmethod
    async def get_all_users_for_messaging(
        db: AsyncSession, current_user_id: int
    ) -> List[dict]:
        """Return all active staff that can be messaged."""
        result = await db.execute(
            select(User)
            .where(User.is_active == True, User.id != current_user_id)
            .order_by(User.role, User.full_name)
        )
        users = result.scalars().all()
        return [
            {"id": u.id, "name": u.full_name, "role": u.role,
             "email": u.email, "department": getattr(u, "department", None)}
            for u in users
        ]
