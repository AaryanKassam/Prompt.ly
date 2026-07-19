"""Ingestion endpoints.

  POST /api/ingest/browser  -> one prompt from the Chrome extension (claude.ai)
  POST /api/ingest/jsonl    -> trigger a local scan of ~/.claude/projects/
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..db import get_session
from ..ingestion.jsonl_parser import parse_all
from ..ingestion.store import ImportResult, upsert_session
from ..models import Prompt, Session

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class BrowserIngest(BaseModel):
    """Payload posted by the Chrome extension for one claude.ai turn."""

    conversation_id: str = Field(alias="conversationId")
    conversation_title: Optional[str] = Field(default=None, alias="conversationTitle")
    timestamp: Optional[datetime] = None
    input_tokens: Optional[int] = Field(default=None, alias="inputTokens")
    output_tokens: Optional[int] = Field(default=None, alias="outputTokens")
    # Present only when the user opts in to text capture.
    prompt_text: Optional[str] = Field(default=None, alias="promptText")
    response_text: Optional[str] = Field(default=None, alias="responseText")
    message_id: Optional[str] = Field(default=None, alias="messageId")
    turn_index: Optional[int] = Field(default=None, alias="turnIndex")

    class Config:
        populate_by_name = True


@router.post("/browser")
def ingest_browser(payload: BrowserIngest, db: DbSession = Depends(get_session)) -> dict:
    external_id = f"browser:{payload.conversation_id}"
    session = db.scalar(select(Session).where(Session.external_id == external_id))
    if session is None:
        session = Session(
            source="browser",
            title=payload.conversation_title,
            conv_id=payload.conversation_id,
            external_id=external_id,
            created_at=payload.timestamp or datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
    elif payload.conversation_title:
        session.title = payload.conversation_title

    # Use the client-supplied turn index, else append after the last known turn.
    turn_index = payload.turn_index
    if turn_index is None:
        max_turn = db.scalar(
            select(func.max(Prompt.turn_index)).where(Prompt.session_id == session.id)
        )
        turn_index = (max_turn or 0) + 1

    prompt = db.scalar(
        select(Prompt).where(Prompt.session_id == session.id, Prompt.turn_index == turn_index)
    )
    if prompt is None:
        prompt = Prompt(session_id=session.id, turn_index=turn_index)
        db.add(prompt)

    prompt.text = payload.prompt_text or prompt.text
    prompt.response_text = payload.response_text or prompt.response_text
    prompt.message_id = payload.message_id or prompt.message_id
    prompt.input_tokens = payload.input_tokens if payload.input_tokens is not None else prompt.input_tokens
    prompt.output_tokens = payload.output_tokens if payload.output_tokens is not None else prompt.output_tokens
    prompt.timestamp = payload.timestamp or prompt.timestamp

    db.commit()
    db.refresh(prompt)
    return {"session_id": session.id, "prompt_id": prompt.id, "turn_index": turn_index}


@router.post("/jsonl")
def ingest_jsonl(db: DbSession = Depends(get_session)) -> dict:
    """Scan ~/.claude/projects/ and import every session (idempotent)."""
    result = ImportResult()
    for parsed in parse_all():
        upsert_session(db, parsed, result)
    db.commit()
    return {
        "sessions_created": result.sessions_created,
        "sessions_updated": result.sessions_updated,
        "prompts_created": result.prompts_created,
    }
