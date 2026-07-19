"""Score endpoints.

  GET  /api/scores/{prompt_id}  -> factor breakdown + signal detail for one prompt
  POST /api/scores/rescore      -> re-run the rubric over every prompt (Phase 1)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import get_session
from ..ingestion.store import score_and_attach
from ..ml.features import extract_signals
from ..models import Prompt, Score

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/{prompt_id}")
def get_score(prompt_id: str, db: DbSession = Depends(get_session)) -> dict:
    prompt = db.get(Prompt, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    score: Score | None = prompt.score
    if score is None:
        raise HTTPException(status_code=404, detail="prompt has no score yet")
    return {
        "prompt_id": prompt.id,
        "overall": score.overall,
        "factors": {
            "clarity": score.clarity,
            "specificity": score.specificity,
            "context": score.context,
            "constraints": score.constraints,
            "scope": score.scope,
            "examples": score.examples,
        },
        "signals": extract_signals(prompt.text or ""),
        "model_phase": score.model_phase,
        "scored_at": score.scored_at,
    }


@router.post("/rescore")
def rescore_all(db: DbSession = Depends(get_session)) -> dict:
    """Re-score every prompt in place (use after tweaking the rubric)."""
    count = 0
    for prompt in db.scalars(select(Prompt)):
        score_and_attach(db, prompt)
        count += 1
    db.commit()
    return {"rescored": count}
