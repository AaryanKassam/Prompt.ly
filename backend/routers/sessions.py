"""Session read endpoints for the dashboard.

  GET /api/sessions        -> list with prompt count + average score
  GET /api/sessions/{id}   -> session detail with its prompt timeline
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..db import get_session
from ..models import Prompt, Score, Session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _diff_summary(file_diffs: dict | None) -> dict:
    d = file_diffs or {}
    return {
        "created": len(d.get("created", []) or []),
        "edited": len(d.get("edited", []) or []),
        "deleted": len(d.get("deleted", []) or []),
    }


@router.get("")
def list_sessions(db: DbSession = Depends(get_session)) -> list[dict]:
    # prompt count + avg overall score per session, newest first.
    rows = db.execute(
        select(
            Session,
            func.count(Prompt.id),
            func.avg(Score.overall),
        )
        .outerjoin(Prompt, Prompt.session_id == Session.id)
        .outerjoin(Score, Score.prompt_id == Prompt.id)
        .group_by(Session.id)
        .order_by(Session.created_at.desc().nullslast())
    ).all()

    return [
        {
            "id": s.id,
            "source": s.source,
            "title": s.title or "(untitled)",
            "project_path": s.project_path,
            "created_at": s.created_at,
            "prompt_count": count,
            "avg_score": round(avg, 2) if avg is not None else None,
        }
        for s, count, avg in rows
    ]


@router.get("/{session_id}")
def get_session_detail(session_id: str, db: DbSession = Depends(get_session)) -> dict:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    prompts = []
    for p in session.prompts:  # ordered by turn_index via relationship
        text = p.text or ""
        prompts.append(
            {
                "id": p.id,
                "turn_index": p.turn_index,
                "text_preview": text[:200] + ("…" if len(text) > 200 else ""),
                "timestamp": p.timestamp,
                "input_tokens": p.input_tokens,
                "output_tokens": p.output_tokens,
                "tool_count": len(p.tool_calls or []),
                "diffs": _diff_summary(p.file_diffs),
                "summary": p.summary,
                "overall": p.score.overall if p.score else None,
            }
        )

    scored = [pr["overall"] for pr in prompts if pr["overall"] is not None]
    return {
        "id": session.id,
        "source": session.source,
        "title": session.title or "(untitled)",
        "project_path": session.project_path,
        "created_at": session.created_at,
        "prompt_count": len(prompts),
        "avg_score": round(sum(scored) / len(scored), 2) if scored else None,
        "prompts": prompts,
    }
