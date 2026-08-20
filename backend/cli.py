"""Prompt.ly terminal interface.

Most Claude Code usage happens in a terminal, so the terminal gets a first-class
UI rather than a curl wrapper. Everything runs against the local database — no
server required — and session logs are re-imported automatically before each
command, so there is nothing to remember to run.

    promptly report                 # report for the folder you're standing in
    promptly report ~/some/project  # ...or a specific one
    promptly score "fix the parser" # grade a draft prompt before sending it
    promptly projects               # every tracked folder
    promptly sync                   # import logs only
    promptly watch                  # live view, refreshes as you work
    promptly install-hook           # auto-sync after every Claude Code session

`--json` is available on report/projects/score for scripting and is what the
VS Code extension consumes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .db import SessionLocal, init_db
from .ml.scorer import active_model_info, score as score_text
from .reports import (
    RECOMMENDATIONS,
    cached_report,
    grade,
    import_sessions,
)
from .workspace import detect_active_workspace, list_open_workspaces

console = Console()

# Score -> colour, matching the dashboard's scale exactly so a 6.4 looks the
# same in the terminal, the sidebar and the browser.
def tone(value: float | None) -> str:
    if value is None:
        return "grey50"
    if value < 5:
        return "red"
    if value < 7:
        return "yellow"
    return "green"


def bar(value: float | None, width: int = 20) -> Text:
    """Horizontal meter for a 0-10 value."""
    if value is None:
        return Text("─" * width, style="grey30")
    filled = round((value / 10) * width)
    t = Text()
    t.append("█" * filled, style=tone(value))
    t.append("░" * (width - filled), style="grey30")
    return t


def resolve_path(raw: str | None) -> str | None:
    """Explicit path, else the folder in focus (cwd wins when it has data)."""
    if raw:
        p = Path(raw).expanduser()
        if not p.is_dir():
            console.print(f"[red]No such folder:[/red] {raw}")
            return None
        return str(p.resolve())

    # In a terminal the working directory IS the intent — prefer it over the
    # editor heuristic, which exists for GUI callers that have no useful cwd.
    cwd = Path.cwd().resolve()
    if cwd != Path.home():
        return str(cwd)
    ws = detect_active_workspace()
    return ws.path if ws else None


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_report(payload: dict, compact: bool = False) -> Group:
    t = payload["totals"]
    name = payload["project_path"].rstrip("/").split("/")[-1]

    if not t["prompts"]:
        return Group(
            Panel(
                Text.from_markup(
                    "No prompts recorded for this folder yet.\n\n"
                    "Use Claude Code here, then run [cyan]promptly sync[/cyan]."
                ),
                title=f"[bold]{name}[/bold]",
                border_style="grey30",
            )
        )

    overall = payload["overall"]

    # Header: score, grade, trend.
    head = Text()
    head.append(f"{overall:.1f}", style=f"bold {tone(overall)}")
    head.append("/10  ", style="grey50")
    head.append(payload["grade"], style=f"bold {tone(overall)}")
    head.append(f"   {t['scored_prompts']} prompts · {t['sessions']} sessions", style="grey50")
    if payload["trend"]:
        tr = payload["trend"]
        arrow = {"improving": "▲", "declining": "▼", "flat": "▬"}[tr["direction"]]
        colour = {"improving": "green", "declining": "red", "flat": "grey50"}[tr["direction"]]
        head.append(f"   {arrow} {tr['direction']}", style=colour)
        if tr["direction"] != "flat":
            head.append(f" {tr['delta']:+.2f}", style=colour)

    factors = Table.grid(padding=(0, 2))
    factors.add_column(justify="right", style="grey62", width=12)
    factors.add_column()
    factors.add_column(justify="right", width=4)
    for factor, value in payload["factors"].items():
        if value is None:
            continue
        label = Text(factor, style="bold white" if factor == payload["weakest_factor"] else "grey62")
        factors.add_row(label, bar(value), Text(f"{value:.1f}", style=tone(value)))

    blocks: list = [
        Panel(head, title=f"[bold]{name}[/bold]", border_style="grey30", padding=(0, 1)),
        Panel(factors, title="factors", border_style="grey30", padding=(0, 1)),
    ]

    if payload["recommendations"] and not compact:
        recs = Table.grid(padding=(0, 1))
        recs.add_column(width=6, justify="right", style="yellow")
        recs.add_column()
        for rec in payload["recommendations"]:
            recs.add_row(f"{rec['missed_pct']}%", Text(rec["advice"], style="white"))
        blocks.append(Panel(recs, title="do these next", border_style="grey30", padding=(0, 1)))

    if payload["worst_prompts"] and not compact:
        # Truncate the preview ourselves rather than letting rich do it: an
        # elastic overflow column steals width from its fixed-width siblings,
        # which collapses the score into an ellipsis.
        limit = max(20, console.width - 16)
        worst = Table.grid(padding=(0, 2))
        worst.add_column(width=4, justify="right")
        worst.add_column()
        for p in payload["worst_prompts"]:
            preview = p["preview"]
            if len(preview) > limit:
                preview = preview[: limit - 1] + "…"
            worst.add_row(
                Text(f"{p['score']:.1f}", style=tone(p["score"])),
                Text(preview, style="grey62"),
            )
        blocks.append(
            Panel(worst, title="lowest-scoring prompts", border_style="grey30", padding=(0, 1))
        )

    footer = Text(
        f"{t['prompts']} prompts · {t['tool_calls']} tool calls · "
        f"{t['files_touched']} files · {t['output_tokens']:,} output tokens",
        style="grey37",
    )
    blocks.append(footer)
    return Group(*blocks)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_report(args: argparse.Namespace) -> int:
    path = resolve_path(args.path)
    if path is None:
        console.print("[red]Could not determine which folder to report on.[/red]")
        return 1

    db = SessionLocal()
    try:
        if not args.no_sync:
            import_sessions(db)
        payload, _ = cached_report(db, path, force=args.refresh)
    finally:
        db.close()

    if args.json:
        print(json.dumps(payload, default=str))
        return 0

    console.print(render_report(payload))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    text = args.text or sys.stdin.read()
    if not text.strip():
        console.print("[red]Nothing to score.[/red] Pass text or pipe it in.")
        return 1

    result = score_text(text)
    if args.json:
        print(
            json.dumps(
                {
                    "overall": round(result.overall, 2),
                    "grade": grade(result.overall),
                    "factors": result.factors,
                    "signals": result.signals,
                    "model_phase": result.model_phase,
                }
            )
        )
        return 0

    head = Text()
    head.append(f"{result.overall:.1f}", style=f"bold {tone(result.overall)}")
    head.append("/10  ", style="grey50")
    head.append(grade(result.overall), style=f"bold {tone(result.overall)}")

    factors = Table.grid(padding=(0, 2))
    factors.add_column(justify="right", style="grey62", width=12)
    factors.add_column()
    factors.add_column(justify="right", width=4)
    for factor, value in sorted(result.factors.items(), key=lambda kv: kv[1]):
        factors.add_row(factor, bar(value), Text(f"{value:.1f}", style=tone(value)))

    blocks = [
        Panel(head, title="prompt score", border_style="grey30", padding=(0, 1)),
        Panel(factors, title="factors", border_style="grey30", padding=(0, 1)),
    ]

    missed = [
        RECOMMENDATIONS[f"{factor}.{name}"]
        for factor, sigs in result.signals.items()
        for name, hit in sigs.items()
        if not hit and f"{factor}.{name}" in RECOMMENDATIONS
    ]
    if missed:
        fixes = Table.grid(padding=(0, 1))
        fixes.add_column(width=2, style="yellow")
        fixes.add_column()
        for advice in missed[:5]:
            fixes.add_row("→", Text(advice, style="white"))
        blocks.append(Panel(fixes, title="to improve", border_style="grey30", padding=(0, 1)))
    else:
        blocks.append(Text("No weaknesses detected — this prompt is well-formed.", style="green"))

    console.print(Group(*blocks))
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    from sqlalchemy import func, select

    from .models import Prompt, Score, Session

    db = SessionLocal()
    try:
        if not args.no_sync:
            import_sessions(db)
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

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "project_path": p,
                        "prompt_count": c,
                        "avg_score": round(a, 2) if a else None,
                    }
                    for p, c, a in rows
                ]
            )
        )
        return 0

    if not rows:
        console.print("[grey62]No projects tracked yet.[/grey62]")
        return 0

    here = str(Path.cwd().resolve())
    table = Table(box=None, pad_edge=False, header_style="grey50")
    table.add_column("score", justify="right", width=6)
    table.add_column("prompts", justify="right", width=8, style="grey62")
    table.add_column("project")
    for path, count, avg in rows:
        marker = Text(" ●", style="green") if path == here else Text("")
        name = Text(path.rstrip("/").split("/")[-1], style="white")
        name.append(marker)
        table.add_row(
            Text(f"{avg:.1f}" if avg else "—", style=tone(avg)),
            str(count),
            name,
        )
    console.print(table)
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        result = import_sessions(db)
    finally:
        db.close()

    if args.json:
        print(json.dumps(result))
        return 0

    console.print(
        f"[green]Synced.[/green] "
        f"{result['sessions_created']} new session(s), "
        f"{result['prompts_created']} new prompt(s)."
    )
    model = active_model_info()
    if model:
        console.print(
            f"[grey50]Scoring with MLP v{model['version']} "
            f"(trained on {model['examples']} prompts).[/grey50]"
        )
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Live report that re-syncs on an interval — leave it open in a split."""
    path = resolve_path(args.path)
    if path is None:
        console.print("[red]Could not determine which folder to watch.[/red]")
        return 1

    def frame() -> Group:
        db = SessionLocal()
        try:
            import_sessions(db)
            payload, _ = cached_report(db, path)
        finally:
            db.close()
        return render_report(payload, compact=args.compact)

    try:
        with Live(frame(), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                time.sleep(args.interval)
                live.update(frame())
    except KeyboardInterrupt:
        return 0


def hook_command() -> str:
    """Absolute path, so the hook doesn't depend on `promptly` being on PATH."""
    launcher = Path(__file__).resolve().parent.parent / "scripts" / "promptly"
    return f"{launcher} sync --json >/dev/null 2>&1 || true"


def _is_promptly_hook(command: str) -> bool:
    """Loose match so hooks written by older versions are still removable."""
    return "promptly" in command and "sync" in command


def cmd_install_hook(args: argparse.Namespace) -> int:
    """Register a Claude Code hook so sessions import themselves.

    Claude Code fires SessionEnd when a session finishes; running the importer
    there means the report is current without anyone remembering a command.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            console.print(f"[red]{settings_path} is not valid JSON — leaving it alone.[/red]")
            return 1

    hooks = settings.setdefault("hooks", {})
    session_end = hooks.setdefault("SessionEnd", [])

    command = hook_command()
    already = any(
        h.get("command") == command
        for entry in session_end
        for h in entry.get("hooks", [])
    )

    if args.uninstall:
        for entry in session_end:
            entry["hooks"] = [
                h for h in entry.get("hooks", []) if not _is_promptly_hook(h.get("command", ""))
            ]
        hooks["SessionEnd"] = [e for e in session_end if e.get("hooks")]
        if not hooks["SessionEnd"]:
            hooks.pop("SessionEnd")
    elif already:
        console.print("[grey62]Hook already installed.[/grey62]")
        return 0
    else:
        # Drop any stale variant before appending the current one.
        for entry in session_end:
            entry["hooks"] = [
                h for h in entry.get("hooks", []) if not _is_promptly_hook(h.get("command", ""))
            ]
        hooks["SessionEnd"] = [e for e in session_end if e.get("hooks")]
        hooks["SessionEnd"].append({"hooks": [{"type": "command", "command": command}]})

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.exists():
        backup = settings_path.with_suffix(".json.promptly-backup")
        backup.write_text(settings_path.read_text())
        console.print(f"[grey50]Backed up -> {backup.name}[/grey50]")
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    verb = "Removed" if args.uninstall else "Installed"
    console.print(f"[green]{verb}[/green] the SessionEnd auto-sync hook in {settings_path}.")
    return 0


def cmd_reclassify(args: argparse.Namespace) -> int:
    """Re-label every stored turn and rescore the ones that are real prompts.

    Needed once after upgrading: rows imported before classification existed
    were all treated as user prompts, including skill injections and command
    echoes, which distorted every average.
    """
    from collections import Counter

    from sqlalchemy import select

    from .ingestion.classify import KIND_USER, classify
    from .ingestion.store import score_and_attach
    from .models import Prompt, ReportCache

    db = SessionLocal()
    try:
        prompts = list(db.scalars(select(Prompt)))
        counts: Counter = Counter()
        changed = 0
        for p in prompts:
            new_kind = classify(p.text)
            if p.kind != new_kind:
                changed += 1
            p.kind = new_kind
            counts[new_kind] += 1
            score_and_attach(db, p)
        # Reports are memoized on prompt counts, which just moved.
        for row in db.scalars(select(ReportCache)):
            db.delete(row)
        db.commit()
    finally:
        db.close()

    if args.json:
        print(json.dumps({"reclassified": changed, "kinds": dict(counts)}))
        return 0

    table = Table(box=None, pad_edge=False, header_style="grey50")
    table.add_column("turns", justify="right", width=6)
    table.add_column("kind")
    for kind, n in counts.most_common():
        style = "green" if kind == KIND_USER else "grey62"
        table.add_row(Text(str(n), style=style), Text(kind, style=style))
    console.print(table)
    console.print(
        f"\n[green]{counts[KIND_USER]}[/green] real prompts scored; "
        f"[grey62]{sum(counts.values()) - counts[KIND_USER]}[/grey62] transcript rows excluded."
    )
    return 0


def cmd_workspaces(args: argparse.Namespace) -> int:
    workspaces = list_open_workspaces()
    if args.json:
        print(json.dumps([w.as_dict() for w in workspaces]))
        return 0
    if not workspaces:
        console.print("[grey62]No editor workspaces detected.[/grey62]")
        return 0
    for w in workspaces:
        console.print(f"[grey50]{w.editor:<16}[/grey50] {w.path}")
    return 0


# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promptly", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, sync=True):
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if sync:
            p.add_argument("--no-sync", action="store_true", help="skip importing new logs first")

    p_report = sub.add_parser("report", help="prompt report for a folder")
    p_report.add_argument("path", nargs="?", help="folder (defaults to the current directory)")
    p_report.add_argument("--refresh", action="store_true", help="rebuild, ignoring the cache")
    add_common(p_report)
    p_report.set_defaults(func=cmd_report)

    p_score = sub.add_parser("score", help="score a draft prompt")
    p_score.add_argument("text", nargs="?", help="prompt text (or pipe it on stdin)")
    add_common(p_score, sync=False)
    p_score.set_defaults(func=cmd_score)

    p_projects = sub.add_parser("projects", help="every tracked folder")
    add_common(p_projects)
    p_projects.set_defaults(func=cmd_projects)

    p_sync = sub.add_parser("sync", help="import new Claude Code session logs")
    p_sync.add_argument("--json", action="store_true")
    p_sync.set_defaults(func=cmd_sync)

    p_watch = sub.add_parser("watch", help="live-updating report")
    p_watch.add_argument("path", nargs="?")
    p_watch.add_argument("--interval", type=float, default=10.0, help="seconds between refreshes")
    p_watch.add_argument("--compact", action="store_true", help="score and factors only")
    p_watch.set_defaults(func=cmd_watch)

    p_hook = sub.add_parser("install-hook", help="auto-sync after each Claude Code session")
    p_hook.add_argument("--uninstall", action="store_true")
    p_hook.set_defaults(func=cmd_install_hook)

    p_rc = sub.add_parser(
        "reclassify", help="re-label stored turns and rescore real prompts"
    )
    p_rc.add_argument("--json", action="store_true")
    p_rc.set_defaults(func=cmd_reclassify)

    p_ws = sub.add_parser("workspaces", help="folders open in VS Code / Cursor")
    p_ws.add_argument("--json", action="store_true")
    p_ws.set_defaults(func=cmd_workspaces)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    init_db()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
