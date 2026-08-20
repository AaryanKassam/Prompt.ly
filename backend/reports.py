"""Build a per-project "prompt report" from stored, already-scored prompts.

This is the payload behind both `GET /api/projects/report` and the MCP server's
`prompt_report` tool. It aggregates the rubric signals across every prompt in a
folder to answer three questions:

  1. How well is this person prompting in this project?  -> overall + grade
  2. Which specific habit is costing them the most?      -> weakest signals
  3. What should they do differently tomorrow?           -> recommendations

Recommendations are derived from *signal hit rates*, not from the overall score,
because "your clarity is 6.2/10" is not actionable but "68% of your prompts never
name a file or line number" is.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .ingestion.classify import KIND_USER, clean
from .ml.features import SIGNALS, extract_signals
from .ml.rubric import WEIGHTS
from .models import Prompt, ReportCache, Score, Session

# One piece of concrete advice per signal, phrased as the fix rather than the flaw.
RECOMMENDATIONS: dict[str, str] = {
    "clarity.single_imperative_verb": "Open with one clear action verb (\"Add…\", \"Fix…\", \"Refactor…\") instead of describing the situation first.",
    "clarity.no_passive_voice": "Say who does what — \"rename the handler\" rather than \"the handler should be renamed\".",
    "clarity.no_hedge_words": "Cut hedges like \"maybe\", \"I think\", \"sort of\". Commit to the request; you can always correct it afterwards.",
    "clarity.sentence_count_le_5": "Keep prompts under ~5 sentences. Long prompts bury the actual ask — split them into separate turns.",
    "specificity.mentions_file_or_line": "Name the file (and line, if you know it). \"Fix the parser\" costs a search; \"fix parse_file in jsonl_parser.py\" doesn't.",
    "specificity.names_exact_function_class": "Reference exact identifiers in backticks — `score_and_attach`, `SessionSummary` — instead of describing them.",
    "specificity.has_concrete_output_format": "State the shape you want back: a JSON schema, a function signature, a table, a diff.",
    "specificity.no_vague_quantifiers": "Replace \"clean it up a bit\" / \"some tests\" with a countable target: \"3 tests covering the empty, single, and 50+ cases\".",
    "context.references_prior_turn": "Anchor follow-ups to what came before (\"building on the parser you just wrote…\") so context isn't reconstructed from scratch.",
    "context.provides_background_why": "Add one clause of why — \"so that re-imports stay idempotent\". Intent lets the model make better judgment calls.",
    "context.mentions_tech_stack": "Name the stack and version when it matters (Next.js 14 App Router, SQLAlchemy 2.0) to rule out wrong-idiom answers.",
    "constraints.has_negative_constraint": "Say what NOT to do — \"don't touch the migrations\", \"no new dependencies\". Negative constraints prevent the most rework.",
    "constraints.specifies_scope_limit": "Bound the blast radius: \"only in backend/ingestion/\", \"leave the tests alone\".",
    "scope.single_task_focus": "One prompt, one task. Bundled asks get uneven attention and are harder to review.",
    "scope.no_compound_and_also": "Split \"and also\" prompts into separate turns — each half gets full effort that way.",
    "scope.task_size_appropriate": "Prompts over ~200 words usually contain 2-3 tasks. Break them up and sequence them.",
    "examples.has_code_block": "Paste the actual code, error, or stack trace in a fenced block rather than paraphrasing it.",
    "examples.has_before_after": "Show current vs. desired: \"currently returns None, should return an empty list\".",
    "examples.has_inline_example": "Give one concrete example of the input/output you have in mind (\"e.g. `parse('a,b')` -> `['a','b']`\").",
}

_ALL_SIGNAL_KEYS = [f"{factor}.{name}" for factor, sigs in SIGNALS.items() for name in sigs]


def grade(score: float | None) -> str:
    """Letter grade for an overall 0-10 score."""
    if score is None:
        return "—"
    if score >= 8.5:
        return "A"
    if score >= 7.5:
        return "B+"
    if score >= 6.5:
        return "B"
    if score >= 5.5:
        return "C+"
    if score >= 4.5:
        return "C"
    if score >= 3.5:
        return "D"
    return "F"


@dataclass
class ReportInputs:
    """Prompts belonging to one project, plus the sessions they came from."""
    project_path: str
    sessions: list[Session]
    prompts: list[Prompt]


def _sort_key(value: datetime | None) -> tuple[int, float]:
    """Chronological sort key that tolerates missing and naive timestamps.

    SQLite hands back naive datetimes even for timezone-aware columns, so
    comparing them against an aware sentinel raises TypeError. Sorting on a
    (has_value, epoch_seconds) tuple sidesteps the comparison entirely and
    keeps undated rows first.
    """
    if value is None:
        return (0, 0.0)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (1, value.timestamp())


def collect(db: DbSession, project_path: str) -> ReportInputs:
    """Load every session/prompt recorded under a project path.

    Matches the exact path and any nested subfolder, so opening a monorepo
    package still picks up sessions recorded at the repo root. The LIKE pattern
    is escaped because project paths routinely contain underscores, which LIKE
    would otherwise treat as single-character wildcards.
    """
    normalized = project_path.rstrip("/")
    prefix = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    sessions = list(
        db.scalars(
            select(Session).where(
                (Session.project_path == normalized)
                | (Session.project_path.like(f"{prefix}/%", escape="\\"))
            )
        )
    )
    prompts: list[Prompt] = []
    for s in sessions:
        # Only turns a person actually typed belong in a report.
        prompts.extend(p for p in s.prompts if (p.kind or KIND_USER) == KIND_USER)
    prompts.sort(key=lambda p: _sort_key(p.timestamp))
    return ReportInputs(project_path=normalized, sessions=sessions, prompts=prompts)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _signal_hit_rates(texts: list[str]) -> dict[str, float]:
    """Fraction of prompts satisfying each signal (0.0-1.0)."""
    if not texts:
        return {}
    totals = {key: 0 for key in _ALL_SIGNAL_KEYS}
    for text in texts:
        results = extract_signals(text)
        for factor, sigs in results.items():
            for name, hit in sigs.items():
                if hit:
                    totals[f"{factor}.{name}"] += 1
    return {key: round(count / len(texts), 3) for key, count in totals.items()}


def _preview(text: str | None, limit: int = 160) -> str:
    t = " ".join(clean(text).split())
    return t[:limit] + ("…" if len(t) > limit else "")


def build_report(db: DbSession, project_path: str) -> dict:
    """Assemble the full report payload for one project folder."""
    data = collect(db, project_path)
    scored = [p for p in data.prompts if p.score and p.score.overall is not None]
    texts = [clean(p.text) for p in data.prompts if clean(p.text)]

    overall = _avg([p.score.overall for p in scored])
    factors = {
        f: _avg([getattr(p.score, f) for p in scored if getattr(p.score, f) is not None])
        for f in WEIGHTS
    }

    # Trend: mean of the first half vs the second half, chronologically.
    trend = None
    if len(scored) >= 6:
        mid = len(scored) // 2
        first = _avg([p.score.overall for p in scored[:mid]])
        second = _avg([p.score.overall for p in scored[mid:]])
        if first is not None and second is not None:
            trend = {
                "first_half": first,
                "second_half": second,
                "delta": round(second - first, 2),
                "direction": "improving" if second > first + 0.15
                else "declining" if second < first - 0.15
                else "flat",
            }

    hit_rates = _signal_hit_rates(texts)
    weakest = sorted(hit_rates.items(), key=lambda kv: kv[1])[:5]
    recommendations = [
        {
            "signal": key,
            "factor": key.split(".")[0],
            "hit_rate": rate,
            "missed_pct": round((1 - rate) * 100),
            "advice": RECOMMENDATIONS[key],
        }
        for key, rate in weakest
        if key in RECOMMENDATIONS
    ]

    ranked = sorted(scored, key=lambda p: p.score.overall, reverse=True)
    def _entry(p: Prompt) -> dict:
        return {
            "id": p.id,
            "session_id": p.session_id,
            "turn_index": p.turn_index,
            "score": round(p.score.overall, 2),
            "preview": _preview(p.text),
        }

    files_touched: set[str] = set()
    created = edited = deleted = 0
    for p in data.prompts:
        d = p.file_diffs or {}
        for bucket in ("created", "edited", "deleted"):
            paths = d.get(bucket) or []
            files_touched.update(paths)
        created += len(d.get("created") or [])
        edited += len(d.get("edited") or [])
        deleted += len(d.get("deleted") or [])

    return {
        "project_path": data.project_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "sessions": len(data.sessions),
            "prompts": len(data.prompts),
            "scored_prompts": len(scored),
            "prompts_with_text": len(texts),
            "input_tokens": sum(p.input_tokens or 0 for p in data.prompts),
            "output_tokens": sum(p.output_tokens or 0 for p in data.prompts),
            "tool_calls": sum(len(p.tool_calls or []) for p in data.prompts),
            "files_touched": len(files_touched),
            "files_created": created,
            "files_edited": edited,
            "files_deleted": deleted,
        },
        "overall": overall,
        "grade": grade(overall),
        "factors": factors,
        "weakest_factor": min(
            ((f, v) for f, v in factors.items() if v is not None),
            key=lambda kv: kv[1],
            default=(None, None),
        )[0],
        "strongest_factor": max(
            ((f, v) for f, v in factors.items() if v is not None),
            key=lambda kv: kv[1],
            default=(None, None),
        )[0],
        "trend": trend,
        "signal_hit_rates": hit_rates,
        "recommendations": recommendations,
        # Split the ranking so a prompt can never appear as both a best and a
        # worst example — with only a handful of scored prompts the naive
        # top-3/bottom-3 slices overlap.
        "best_prompts": [_entry(p) for p in ranked[: min(3, len(ranked) // 2)]],
        "worst_prompts": [
            _entry(p) for p in ranked[-min(3, len(ranked) // 2) :][::-1]
        ]
        if len(ranked) >= 2
        else [],
        "sessions": [
            {
                "id": s.id,
                "title": s.title or "(untitled)",
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "prompt_count": len(s.prompts),
            }
            for s in sorted(data.sessions, key=lambda s: _sort_key(s.created_at), reverse=True)
        ],
    }


SIGNAL_LABELS: dict[str, str] = {
    "single_imperative_verb": "opens with one action verb",
    "no_passive_voice": "active voice",
    "no_hedge_words": "no hedging",
    "sentence_count_le_5": "5 sentences or fewer",
    "mentions_file_or_line": "names a file or line",
    "names_exact_function_class": "names exact identifiers",
    "has_concrete_output_format": "states output format",
    "no_vague_quantifiers": "no vague quantifiers",
    "references_prior_turn": "anchors to prior turn",
    "provides_background_why": "explains why",
    "mentions_tech_stack": "names the stack",
    "has_negative_constraint": "says what not to do",
    "specifies_scope_limit": "bounds the scope",
    "single_task_focus": "one task",
    "no_compound_and_also": "no compound asks",
    "task_size_appropriate": "right size",
    "has_code_block": "includes code",
    "has_before_after": "shows before/after",
    "has_inline_example": "gives an example",
}


def factor_evidence(db: DbSession, project_path: str, factor: str, limit: int = 10) -> dict:
    """Which recent prompts pushed one factor up or down.

    A factor score is otherwise an unexplained number. This returns the last
    `limit` prompts with their per-signal pass/fail for that factor, so the bar
    can be expanded into the evidence behind it.
    """
    if factor not in SIGNALS:
        return {"factor": factor, "error": "unknown factor"}

    data = collect(db, project_path)
    recent = [p for p in data.prompts if clean(p.text)][-limit:][::-1]

    signal_names = list(SIGNALS[factor])
    entries = []
    for p in recent:
        results = extract_signals(clean(p.text))[factor]
        met = sum(1 for hit in results.values() if hit)
        entries.append({
            "id": p.id,
            "session_id": p.session_id,
            "turn_index": p.turn_index,
            "preview": _preview(p.text, 120),
            "factor_score": round(10.0 * met / len(signal_names), 1) if signal_names else None,
            "met": met,
            "total": len(signal_names),
            "signals": [
                {"name": n, "label": SIGNAL_LABELS.get(n, n.replace("_", " ")), "met": bool(results[n])}
                for n in signal_names
            ],
        })

    # Per-signal hit counts across this window, so the weakest habit is visible.
    breakdown = [
        {
            "name": n,
            "label": SIGNAL_LABELS.get(n, n.replace("_", " ")),
            "met": sum(1 for e in entries if e["signals"][i]["met"]),
            "total": len(entries),
        }
        for i, n in enumerate(signal_names)
    ]

    return {
        "factor": factor,
        "weight": WEIGHTS.get(factor),
        "window": len(entries),
        "breakdown": breakdown,
        "prompts": entries,
    }


def fingerprint(db: DbSession, project_path: str) -> str:
    """Cheap signature of the data a report would be built from.

    Prompts are only ever appended by the importer and rescoring bumps a
    score's `scored_at`, so row count + newest prompt id + latest scoring time
    is enough to tell a stale cache entry from a live one.
    """
    data = collect(db, project_path)
    ids = [p.id for p in data.prompts]
    if not ids:
        return "empty"
    latest = db.scalar(select(func.max(Score.scored_at)).where(Score.prompt_id.in_(ids)))
    return f"{len(ids)}:{max(ids)}:{latest.isoformat() if latest else '-'}"


def cached_report(
    db: DbSession, project_path: str, force: bool = False
) -> tuple[dict, bool]:
    """Report for a folder, rebuilt only when the underlying data has moved.

    Returns (payload, was_cached). Shared by the HTTP API and the MCP server so
    both surfaces read and write the same cache rows.
    """
    normalized = project_path.rstrip("/")
    fp = fingerprint(db, normalized)
    row = db.scalar(select(ReportCache).where(ReportCache.project_path == normalized))

    if row is not None and row.fingerprint == fp and not force:
        return row.payload, True

    payload = build_report(db, normalized)
    if row is None:
        db.add(ReportCache(project_path=normalized, fingerprint=fp, payload=payload))
    else:
        row.fingerprint, row.payload = fp, payload
    db.commit()
    return payload, False


def import_sessions(db: DbSession) -> dict:
    """Pull any new Claude Code session logs into the database."""
    from .ingestion.jsonl_parser import parse_all
    from .ingestion.store import ImportResult, upsert_session

    result = ImportResult()
    for parsed in parse_all():
        upsert_session(db, parsed, result)
    db.commit()
    return {
        "sessions_created": result.sessions_created,
        "prompts_created": result.prompts_created,
    }


def render_markdown(report: dict) -> str:
    """Human-readable rendering, used by the MCP tool output."""
    t = report["totals"]
    lines = [
        f"# Prompt report — `{report['project_path']}`",
        "",
    ]
    if not t["prompts"]:
        lines.append(
            "No prompts recorded for this folder yet. Run `python scripts/import_jsonl.py` "
            "after using Claude Code here, then ask again."
        )
        return "\n".join(lines)

    lines += [
        f"**{report['overall']}/10** ({report['grade']}) across "
        f"{t['scored_prompts']} scored prompts in {t['sessions']} session(s).",
        "",
    ]
    if report["trend"]:
        tr = report["trend"]
        arrow = {"improving": "↑", "declining": "↓", "flat": "→"}[tr["direction"]]
        lines += [
            f"Trend: {arrow} {tr['direction']} "
            f"({tr['first_half']} → {tr['second_half']}, {tr['delta']:+})",
            "",
        ]

    lines += ["## Factor breakdown", ""]
    for factor, value in sorted(
        report["factors"].items(), key=lambda kv: (kv[1] is None, kv[1])
    ):
        if value is None:
            continue
        filled = round(value)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"- `{bar}` **{factor}** {value}/10")

    if report["recommendations"]:
        lines += ["", "## Do these next", ""]
        for i, rec in enumerate(report["recommendations"], 1):
            lines.append(f"{i}. **{rec['missed_pct']}% of prompts miss this** — {rec['advice']}")

    if report["worst_prompts"]:
        lines += ["", "## Lowest-scoring prompts", ""]
        for p in report["worst_prompts"]:
            lines.append(f"- **{p['score']}/10** — \"{p['preview']}\"")

    lines += [
        "",
        "## Activity",
        "",
        f"- {t['prompts']} prompts, {t['tool_calls']} tool calls",
        f"- {t['files_touched']} distinct files touched "
        f"({t['files_created']} created, {t['files_edited']} edited, {t['files_deleted']} deleted)",
        f"- {t['input_tokens']:,} input / {t['output_tokens']:,} output tokens",
    ]
    return "\n".join(lines)
