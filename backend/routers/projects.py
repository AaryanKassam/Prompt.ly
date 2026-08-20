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
    fingerprint,
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
    # Group by the prompt's own attribution, falling back to its session's cwd,
    # so a project's totals match what its report shows.
    owner = func.coalesce(Prompt.project_path, Session.project_path)
    rows = db.execute(
        select(
            owner,
            func.count(func.distinct(Session.id)),
            func.count(Prompt.id),
            func.avg(Score.overall),
            func.max(Session.created_at),
        )
        .select_from(Prompt)
        .join(Session, Prompt.session_id == Session.id)
        .outerjoin(Score, Score.prompt_id == Prompt.id)
        .where(owner.is_not(None))
        .where(Prompt.kind == "user")
        .group_by(owner)
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


@router.get("/playbook")
def get_playbook(
    path: str | None = Query(None),
    db: DbSession = Depends(get_session),
) -> dict:
    """Return a stored playbook, if one has been generated for this project."""
    from ..models import Playbook
    from ..llm import available

    resolved = _resolve_path(path)
    row = db.scalar(select(Playbook).where(Playbook.project_path == resolved))
    payload, _ = cached_report(db, resolved)
    current = fingerprint(db, resolved)

    if row is None:
        return {"exists": False, "llm_available": available(), "project_path": resolved}
    return {
        "exists": True,
        "llm_available": available(),
        "project_path": resolved,
        "markdown": row.markdown,
        "generated_at": row.generated_at,
        "model": row.model,
        "stale": row.fingerprint != current,
        "usage": {"input_tokens": row.input_tokens, "output_tokens": row.output_tokens},
    }


@router.post("/playbook")
def create_playbook(
    path: str | None = Query(None),
    force: bool = Query(False, description="Regenerate even if a current one exists"),
    db: DbSession = Depends(get_session),
) -> dict:
    """Generate the personalised prompting guide behind the Execute button.

    This is the only endpoint that calls a language model. Everything it is
    given — the weaknesses, the percentages, the example prompts — was measured
    locally first; the model only turns those measurements into prose and
    rewrites.
    """
    from ..llm import LLMUnavailable, generate_playbook
    from ..models import Playbook

    resolved = _resolve_path(path)
    report, _ = cached_report(db, resolved)
    if not report["totals"]["prompts"]:
        raise HTTPException(status_code=400, detail="no prompts recorded for this project")

    current = fingerprint(db, resolved)
    row = db.scalar(select(Playbook).where(Playbook.project_path == resolved))
    if row is not None and row.fingerprint == current and not force:
        return {"markdown": row.markdown, "cached": True, "generated_at": row.generated_at}

    try:
        result = generate_playbook(report, report.get("worst_prompts", []))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    from ..llm import MODEL

    if row is None:
        row = Playbook(project_path=resolved, fingerprint=current, markdown=result.markdown)
        db.add(row)
    else:
        row.fingerprint, row.markdown = current, result.markdown
    row.model = MODEL
    row.input_tokens = result.input_tokens
    row.output_tokens = result.output_tokens
    db.commit()

    return {
        "markdown": result.markdown,
        "cached": False,
        "generated_at": row.generated_at,
        "usage": result.as_dict()["usage"],
    }


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
