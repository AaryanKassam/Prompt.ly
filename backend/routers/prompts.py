"""Prompt detail + annotation endpoints.

  GET   /api/prompts/{id}             -> full prompt with score breakdown + signals
  PATCH /api/prompts/{id}/annotation  -> upsert user note + tags
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..db import get_session
from ..ml.features import extract_signals
from ..models import Annotation, Prompt

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class AnnotationIn(BaseModel):
    note: Optional[str] = None
    tags: Optional[list[str]] = None


def _score_block(prompt: Prompt) -> Optional[dict]:
    s = prompt.score
    if s is None:
        return None
    return {
        "overall": s.overall,
        "model_phase": s.model_phase,
        "factors": {
            "clarity": s.clarity,
            "specificity": s.specificity,
            "context": s.context,
            "constraints": s.constraints,
            "scope": s.scope,
            "examples": s.examples,
        },
    }


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str, db: DbSession = Depends(get_session)) -> dict:
    p = db.get(Prompt, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    ann = p.annotation
    return {
        "id": p.id,
        "session_id": p.session_id,
        "turn_index": p.turn_index,
        "text": p.text,
        "response_text": p.response_text,
        "model": p.model,
        "input_tokens": p.input_tokens,
        "output_tokens": p.output_tokens,
        "timestamp": p.timestamp,
        "tool_calls": p.tool_calls or [],
        "file_diffs": p.file_diffs or {"created": [], "edited": [], "deleted": []},
        "summary": p.summary,
        "score": _score_block(p),
        "signals": extract_signals(p.text or ""),
        "annotation": {"note": ann.note, "tags": ann.tags or []} if ann else None,
    }


@router.patch("/{prompt_id}/annotation")
def upsert_annotation(
    prompt_id: str, payload: AnnotationIn, db: DbSession = Depends(get_session)
) -> dict:
    p = db.get(Prompt, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="prompt not found")

    ann = p.annotation or Annotation(prompt_id=p.id)
    if payload.note is not None:
        ann.note = payload.note
    if payload.tags is not None:
        ann.tags = payload.tags
    ann.updated_at = datetime.now(timezone.utc)
    p.annotation = ann
    db.add(ann)
    db.commit()
    return {"note": ann.note, "tags": ann.tags or []}
