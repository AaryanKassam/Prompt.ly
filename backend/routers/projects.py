"""Project-scoped endpoints backing the workspace report.

  GET  /api/projects                -> every project path Prompt.ly has data for
  GET  /api/projects/workspaces     -> folders currently open in VS Code / Cursor
  GET  /api/projects/active         -> best guess at the folder in focus right now
  GET  /api/projects/report         -> cached prompt report for a folder
  POST /api/projects/report/refresh -> re-import + rebuild, bypassing the cache
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..db import get_session
from ..models import Prompt, Score, Session
from ..reports import (
    cached_report,
    collect,
    factor_evidence,
    import_sessions,
    render_markdown,
)
from ..workspace import detect_active_workspace, list_open_workspaces

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _resolve_path(path: str | None) -> str:
    """Fall back to the detected editor workspace when no path is given."""
    if path:
        return path
    ws = detect_active_workspace()
    if ws is None:
        raise HTTPException(
            status_code=404,
            detail="No editor workspace detected. Pass ?path= explicitly.",
        )
    return ws.path


@router.get("")
def list_projects(db: DbSession = Depends(get_session)) -> list[dict]:
    """Every project path with recorded sessions, busiest first."""
    rows = db.execute(
        select(
            Session.project_path,
            func.count(func.distinct(Session.id)),
            func.count(Prompt.id),
            func.avg(Score.overall),
            func.max(Session.created_at),
        )
        .outerjoin(Prompt, Prompt.session_id == Session.id)
        .outerjoin(Score, Score.prompt_id == Prompt.id)
        .where(Session.project_path.is_not(None))
        .group_by(Session.project_path)
        .order_by(func.count(Prompt.id).desc())
    ).all()

    return [
        {
            "project_path": path,
            "name": (path or "").rstrip("/").split("/")[-1] or path,
            "session_count": sessions,
            "prompt_count": prompts,
            "avg_score": round(avg, 2) if avg is not None else None,
            "last_active": last,
        }
        for path, sessions, prompts, avg, last in rows
    ]


@router.get("/workspaces")
def workspaces() -> list[dict]:
    """Folders open in a detected editor, most recently active first."""
    return [w.as_dict() for w in list_open_workspaces()]


@router.get("/active")
def active_workspace(db: DbSession = Depends(get_session)) -> dict:
    """The folder Prompt.ly thinks you're working in, plus whether it has data."""
    ws = detect_active_workspace()
    if ws is None:
        return {"detected": False}
    data = collect(db, ws.path)
    return {
        "detected": True,
        **ws.as_dict(),
        "has_data": bool(data.prompts),
        "prompt_count": len(data.prompts),
    }


@router.get("/report")
def project_report(
    path: str | None = Query(None, description="Folder path; auto-detected when omitted"),
    fmt: str = Query("json", pattern="^(json|markdown)$"),
    refresh: bool = Query(False, description="Bypass the cache and rebuild"),
    db: DbSession = Depends(get_session),
) -> dict:
    payload, was_cached = cached_report(db, _resolve_path(path), force=refresh)
    if fmt == "markdown":
        return {
            "project_path": payload["project_path"],
            "cached": was_cached,
            "markdown": render_markdown(payload),
        }
    return {**payload, "cached": was_cached}


@router.get("/factor")
def factor_detail(
    factor: str = Query(..., description="clarity | specificity | context | constraints | scope | examples"),
    path: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: DbSession = Depends(get_session),
) -> dict:
    """Evidence behind one factor score: recent prompts and their signals."""
    result = factor_evidence(db, _resolve_path(path), factor, limit=limit)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/report/refresh")
def refresh_report(
    path: str | None = Query(None),
    reimport: bool = Query(True, description="Re-read Claude Code logs before rebuilding"),
    db: DbSession = Depends(get_session),
) -> dict:
    resolved = _resolve_path(path)
    imported = import_sessions(db) if reimport else None
    payload, _ = cached_report(db, resolved, force=True)
    return {**payload, "cached": False, "imported": imported}
