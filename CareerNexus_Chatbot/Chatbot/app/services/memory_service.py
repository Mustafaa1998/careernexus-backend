# app/services/memory_service.py
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMemory


async def save_message(db: AsyncSession, session_id: str, role: str, content: str):
    msg = ChatMemory(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    return msg


async def get_history(db: AsyncSession, session_id: str, limit: int = 15) -> List[ChatMemory]:
    result = await db.execute(
        select(ChatMemory)
        .where(ChatMemory.session_id == session_id)
        .order_by(ChatMemory.created_at.desc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    items.reverse()
    return items


async def save_profile_snapshot(db: AsyncSession, session_id: str, profile_data: Dict[str, Any]):
    # store as a special role in same table (no schema changes)
    await save_message(db, session_id=session_id, role="profile_snapshot", content=json.dumps(profile_data))


async def get_latest_profile_snapshot(db: AsyncSession, session_id: str) -> Optional[Dict[str, Any]]:
    result = await db.execute(
        select(ChatMemory)
        .where(ChatMemory.session_id == session_id, ChatMemory.role == "profile_snapshot")
        .order_by(ChatMemory.created_at.desc())
        .limit(1)
    )
    row = result.scalars().first()
    if not row:
        return None
    try:
        return json.loads(row.content)
    except Exception:
        return None
