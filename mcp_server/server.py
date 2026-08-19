"""Prompt.ly MCP server — the Claude-app-side surface of the project.

Exposes Prompt.ly's scoring and reporting over stdio so it can be added to the
Claude desktop app (and Claude Code) as an extension. Once installed, asking
Claude "how are my prompts in this project?" auto-detects the folder open in
VS Code, serves a cached report, and only rescans when new prompts have landed.

Deliberately talks to the database *directly* rather than to the FastAPI server:
an extension that only works while a separate `uvicorn` process happens to be
running is an extension that mostly doesn't work.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The server is launched by the Claude app from an arbitrary working directory,
# so put the repo root on the path before importing the backend package.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.ml.scorer import active_model_info, score  # noqa: E402
from backend.reports import (  # noqa: E402
    cached_report,
    import_sessions,
    render_markdown,
)
from backend.workspace import detect_active_workspace, list_open_workspaces  # noqa: E402

mcp = MCPServer(
    name="promptly",
    title="Prompt.ly",
    version="1.0.0",
    instructions=(
        "Prompt.ly analyses how effectively the user writes prompts. "
        "Call `prompt_report` when they ask how they're doing, how their prompting "
        "looks in this project, or for a prompt report — it auto-detects the folder "
        "open in their editor, so a path is rarely needed. Call `score_draft_prompt` "
        "when they want feedback on a prompt before sending it."
    ),
)


def _resolve_path(path: str | None) -> tuple[str | None, str | None]:
    """Return (resolved_path, error_message)."""
    if path:
        p = Path(path).expanduser()
        if not p.is_dir():
            return None, f"No such folder: {path}"
        return str(p.resolve()), None

    ws = detect_active_workspace()
    if ws is None:
        return None, (
            "Couldn't detect an open editor folder. Pass `path` explicitly, or set "
            "the PROMPTLY_WORKSPACE environment variable."
        )
    return ws.path, None


@mcp.tool(
    description=(
        "Prompt-quality report for a project folder. Auto-detects the folder currently "
        "open in VS Code / Cursor when `path` is omitted. Results are cached and only "
        "recomputed when new prompts have been recorded."
    )
)
def prompt_report(path: str | None = None, refresh: bool = False) -> str:
    project_path, err = _resolve_path(path)
    if err:
        return err

    db = SessionLocal()
    try:
        if refresh:
            import_sessions(db)
        payload, was_cached = cached_report(db, project_path, force=refresh)

        # An empty report usually just means the importer hasn't run yet.
        if not payload["totals"]["prompts"] and not refresh:
            import_sessions(db)
            payload, was_cached = cached_report(db, project_path, force=True)

        md = render_markdown(payload)
        footer = "_cached_" if was_cached else "_freshly computed_"
        return f"{md}\n\n---\n{footer} · full dashboard: http://localhost:3000/projects"
    finally:
        db.close()


@mcp.tool(
    description=(
        "Score a draft prompt 0-10 across clarity, specificity, context, constraints, "
        "scope and examples, with concrete suggestions — use before sending a prompt."
    )
)
def score_draft_prompt(text: str) -> str:
    from backend.reports import RECOMMENDATIONS, grade

    result = score(text)
    lines = [
        f"**{result.overall:.1f}/10** ({grade(result.overall)})",
        "",
    ]
    for factor, value in sorted(result.factors.items(), key=lambda kv: kv[1]):
        filled = round(value)
        lines.append(f"- `{'█' * filled}{'░' * (10 - filled)}` **{factor}** {value:.1f}/10")

    missed = [
        RECOMMENDATIONS[f"{factor}.{name}"]
        for factor, sigs in result.signals.items()
        for name, hit in sigs.items()
        if not hit and f"{factor}.{name}" in RECOMMENDATIONS
    ]
    if missed:
        lines += ["", "**To improve this prompt:**", ""]
        lines += [f"- {advice}" for advice in missed[:5]]
    else:
        lines += ["", "No weaknesses detected — this prompt is well-formed."]
    return "\n".join(lines)


@mcp.tool(
    description="Folders currently open in VS Code / Cursor, most recently active first."
)
def detect_workspace() -> str:
    active = detect_active_workspace()
    others = list_open_workspaces(limit=8)
    if active is None and not others:
        return "No editor workspaces detected."

    lines = []
    if active:
        lines += [f"**Active:** `{active.path}` (via {active.editor})", ""]
    if others:
        lines += ["**Recently open:**", ""]
        lines += [f"- `{w.path}` — {w.editor}" for w in others]
    return "\n".join(lines)


@mcp.tool(
    description="All project folders Prompt.ly has recorded prompts for, with average scores."
)
def list_tracked_projects() -> str:
    from sqlalchemy import func, select

    from backend.models import Prompt, Score, Session

    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                Session.project_path,
                func.count(Prompt.id),
                func.avg(Score.overall),
            )
            .outerjoin(Prompt, Prompt.session_id == Session.id)
            .outerjoin(Score, Score.prompt_id == Prompt.id)
            .where(Session.project_path.is_not(None))
            .group_by(Session.project_path)
            .order_by(func.count(Prompt.id).desc())
        ).all()
    finally:
        db.close()

    if not rows:
        return "No projects tracked yet. Run `python scripts/import_jsonl.py` first."
    return "\n".join(
        f"- `{path}` — {count} prompts, avg {round(avg, 2) if avg else '—'}/10"
        for path, count, avg in rows
    )


@mcp.tool(
    description="Re-read Claude Code session logs and rebuild the report for a folder."
)
def refresh_data(path: str | None = None) -> str:
    project_path, err = _resolve_path(path)
    if err:
        return err

    db = SessionLocal()
    try:
        imported = import_sessions(db)
        payload, _ = cached_report(db, project_path, force=True)
        model = active_model_info()
        model_line = (
            f"Scoring model: MLP v{model['version']} (trained on {model['examples']} prompts)"
            if model
            else "Scoring model: rubric (no trained MLP active yet)"
        )
        return (
            f"Imported {imported['sessions_created']} new session(s), "
            f"{imported['prompts_created']} new prompt(s).\n"
            f"{model_line}\n\n{render_markdown(payload)}"
        )
    finally:
        db.close()


def main() -> None:
    init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
