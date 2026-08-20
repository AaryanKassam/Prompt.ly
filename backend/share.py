"""Build a redacted, shareable prompt-quality report.

The dashboard is an internal tool: it shows prompt text, file paths and session
titles because the person reading it wrote them. None of that can be handed to
an employer — session titles alone ("Set up HealthLink application from handoff
document") describe unreleased work, and prompt text is worse.

This module produces a self-contained artefact carrying only aggregate,
non-reversible numbers. Redaction is a **whitelist**: `redacted_payload` names
every field it copies, so a future field added to the report cannot silently
leak into a shared file. That is the whole reason it isn't written as a
blacklist of keys to strip.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .ml.rubric import WEIGHTS
from .reports import SIGNAL_LABELS, grade
from .validation import run_benchmark

# Factor -> what it measures, in language a non-user can follow.
FACTOR_MEANING = {
    "clarity": "States one unambiguous action in active voice",
    "specificity": "Names files, identifiers and the expected output shape",
    "context": "Supplies background, intent and the relevant stack",
    "constraints": "Bounds the work — what not to change, where to stop",
    "scope": "One task per request, sized to be reviewable",
    "examples": "Shows code, errors, or a concrete input/output case",
}


def redacted_payload(report: dict, anonymize: bool = False) -> dict:
    """Aggregate-only view of a project report.

    Whitelist by construction: every value below is either a number, a fixed
    label from this codebase, or generic advice text. No prompt content, no file
    paths, no session titles.
    """
    totals = report.get("totals", {}) or {}
    name = (report.get("project_path") or "").rstrip("/").split("/")[-1]

    return {
        "schema": "promptly.share/1",
        "project": "Project A" if anonymize else (name or "Project"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": report.get("overall"),
        "grade": report.get("grade"),
        "trend": report.get("trend"),
        # Counts only — never the files or prompts themselves.
        "volume": {
            "prompts_scored": totals.get("scored_prompts", 0),
            "prompts_total": totals.get("prompts", 0),
            "sessions": totals.get("sessions", 0),
            "tool_calls": totals.get("tool_calls", 0),
            "files_touched": totals.get("files_touched", 0),
            "output_tokens": totals.get("output_tokens", 0),
        },
        "factors": [
            {
                "name": f,
                "score": (report.get("factors") or {}).get(f),
                "weight": WEIGHTS[f],
                "measures": FACTOR_MEANING[f],
            }
            for f in WEIGHTS
        ],
        # Hit rates are ratios over the whole project; they cannot be inverted
        # to recover an individual prompt.
        "habits": [
            {
                "label": SIGNAL_LABELS.get(key.split(".")[1], key),
                "factor": key.split(".")[0],
                "hit_rate": rate,
            }
            for key, rate in sorted(
                (report.get("signal_hit_rates") or {}).items(), key=lambda kv: kv[1]
            )
        ],
        # Advice strings are constants from reports.py, not user content.
        "focus_areas": [
            {"missed_pct": r["missed_pct"], "factor": r["factor"], "advice": r["advice"]}
            for r in report.get("recommendations", [])
        ],
        "methodology": {
            "factors": len(WEIGHTS),
            "signals": sum(len(v) for v in __import__(
                "backend.ml.features", fromlist=["SIGNALS"]
            ).SIGNALS.values()),
            "scoring": "Deterministic rule-based rubric; no language model involved.",
        },
    }


def _bar(pct: float, tone: str) -> str:
    return (
        f'<div class="track"><div class="fill {tone}" style="width:{pct:.1f}%"></div></div>'
    )


def _tone(value: float | None) -> str:
    if value is None:
        return "none"
    return "low" if value < 5 else "mid" if value < 7 else "high"


def render_html(payload: dict, benchmark: dict | None = None) -> str:
    """Self-contained HTML: no external assets, prints cleanly to PDF."""
    e = html.escape
    overall = payload["overall"]
    score_text = f"{overall:.1f}" if isinstance(overall, (int, float)) else "—"

    factor_rows = "".join(
        f"""<tr>
              <th scope="row">{e(f['name'].title())}
                <span class="weight">{round(f['weight'] * 100)}%</span>
                <span class="means">{e(f['measures'])}</span>
              </th>
              <td class="barcell">{_bar((f['score'] or 0) * 10, _tone(f['score']))}</td>
              <td class="num">{f['score'] if f['score'] is not None else '—'}</td>
            </tr>"""
        for f in payload["factors"]
    )

    habit_rows = "".join(
        f"""<tr>
              <th scope="row">{e(h['label'])}<span class="means">{e(h['factor'])}</span></th>
              <td class="barcell">{_bar(h['hit_rate'] * 100, _tone(h['hit_rate'] * 10))}</td>
              <td class="num">{round(h['hit_rate'] * 100)}%</td>
            </tr>"""
        for h in payload["habits"]
    )

    focus = "".join(
        f"""<li><span class="pct">{f['missed_pct']}%</span>
             <span>{e(f['advice'])}</span></li>"""
        for f in payload["focus_areas"]
    )

    trend = payload.get("trend")
    trend_html = ""
    if trend:
        arrow = {"improving": "▲", "declining": "▼", "flat": "▬"}[trend["direction"]]
        trend_html = (
            f'<span class="trend {trend["direction"]}">{arrow} '
            f'{e(trend["direction"])} {trend["delta"]:+.2f}</span>'
        )

    v = payload["volume"]
    bench_html = ""
    if benchmark:
        bench_html = f"""
        <p class="bench">Validated on a {benchmark['pairs']}-pair benchmark in which the same
        request is written once weakly and once well: the scorer ranked the stronger version
        higher in <strong>{benchmark['pairs_correct']} of {benchmark['pairs']}</strong> pairs
        (AUC {benchmark['auc']}).</p>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prompt quality report — {e(payload['project'])}</title>
<style>
  :root {{
    --bg:#fff; --fg:#111827; --muted:#6b7280; --faint:#9ca3af;
    --line:#e5e7eb; --panel:#f9fafb;
    --low:#dc2626; --mid:#d97706; --high:#059669; --none:#d1d5db;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0f172a; --fg:#f8fafc; --muted:#94a3b8; --faint:#64748b;
      --line:#1f2a3f; --panel:#151e33;
      --low:#ef4444; --mid:#f59e0b; --high:#22c55e; --none:#334155;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:40px 24px; background:var(--bg); color:var(--fg);
    font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .sheet {{ max-width:760px; margin:0 auto; }}
  header {{ display:flex; justify-content:space-between; align-items:flex-start;
    gap:24px; padding-bottom:20px; border-bottom:1px solid var(--line); }}
  h1 {{ font-size:19px; margin:0 0 4px; letter-spacing:-.01em; }}
  .sub {{ color:var(--muted); font-size:13px; margin:0; }}
  .scorebox {{ text-align:right; flex-shrink:0; }}
  .score {{ font-size:44px; font-weight:650; line-height:1; font-variant-numeric:tabular-nums; }}
  .grade {{ font-size:15px; color:var(--muted); margin-left:6px; }}
  .trend {{ display:block; font-size:12px; margin-top:6px; }}
  .trend.improving {{ color:var(--high); }} .trend.declining {{ color:var(--low); }}
  .trend.flat {{ color:var(--muted); }}
  h2 {{ font-size:11px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--faint); margin:32px 0 10px; font-weight:600; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; font-weight:500; padding:7px 0; vertical-align:top; }}
  td {{ padding:7px 0; vertical-align:middle; }}
  .weight {{ color:var(--faint); font-size:11px; margin-left:6px; font-variant-numeric:tabular-nums; }}
  .means {{ display:block; color:var(--muted); font-size:11.5px; font-weight:400; margin-top:1px; }}
  .barcell {{ width:46%; padding-left:16px; padding-right:12px; }}
  .track {{ height:7px; background:var(--panel); border-radius:4px; overflow:hidden;
    border:1px solid var(--line); }}
  .fill {{ height:100%; border-radius:4px; }}
  .fill.low{{background:var(--low)}} .fill.mid{{background:var(--mid)}}
  .fill.high{{background:var(--high)}} .fill.none{{background:var(--none)}}
  .num {{ text-align:right; width:52px; font-variant-numeric:tabular-nums; color:var(--muted); }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:10px; }}
  .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:11px 13px; }}
  .stat .k {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--faint); }}
  .stat .v {{ font-size:19px; font-weight:600; font-variant-numeric:tabular-nums; margin-top:3px; }}
  ol.focus {{ list-style:none; padding:0; margin:0; }}
  ol.focus li {{ display:flex; gap:12px; padding:9px 0; border-top:1px solid var(--line); }}
  ol.focus li:first-child {{ border-top:none; }}
  .pct {{ font-weight:650; color:var(--mid); font-variant-numeric:tabular-nums;
    min-width:38px; flex-shrink:0; }}
  .note {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
    padding:14px 16px; font-size:12.5px; color:var(--muted); }}
  .note strong {{ color:var(--fg); }}
  .note ul {{ margin:6px 0 0; padding-left:18px; }}
  .bench {{ font-size:12.5px; color:var(--muted); margin:10px 0 0; }}
  footer {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--line);
    font-size:11.5px; color:var(--faint); display:flex; justify-content:space-between; gap:16px; }}
  @media print {{
    body {{ padding:0; }}
    :root {{ --bg:#fff; --fg:#111827; --panel:#f9fafb; --line:#e5e7eb; }}
    h2 {{ page-break-after:avoid; }} table,ol.focus {{ page-break-inside:avoid; }}
  }}
</style></head>
<body><div class="sheet">

<header>
  <div>
    <h1>Prompt quality report</h1>
    <p class="sub">{e(payload['project'])} · generated {e(payload['generated_at'][:10])}</p>
  </div>
  <div class="scorebox">
    <div class="score">{score_text}<span class="grade">{e(payload['grade'] or '')}</span></div>
    {trend_html}
  </div>
</header>

<h2>Quality factors</h2>
<table><tbody>{factor_rows}</tbody></table>

<h2>Volume</h2>
<div class="stats">
  <div class="stat"><div class="k">Prompts</div><div class="v">{v['prompts_scored']}</div></div>
  <div class="stat"><div class="k">Sessions</div><div class="v">{v['sessions']}</div></div>
  <div class="stat"><div class="k">Tool calls</div><div class="v">{v['tool_calls']}</div></div>
  <div class="stat"><div class="k">Files touched</div><div class="v">{v['files_touched']}</div></div>
  <div class="stat"><div class="k">Output tokens</div><div class="v">{v['output_tokens']:,}</div></div>
</div>

<h2>Habit frequency — share of prompts meeting each signal</h2>
<table><tbody>{habit_rows}</tbody></table>

<h2>Focus areas</h2>
<ol class="focus">{focus}</ol>

<h2>How this is measured</h2>
<div class="note">
  Every prompt is scored 0–10 across {payload['methodology']['factors']} weighted factors
  built from {payload['methodology']['signals']} structural signals.
  {e(payload['methodology']['scoring'])}
  {bench_html}
</div>

<h2>What this file contains</h2>
<div class="note">
  <strong>Included:</strong> aggregate scores, factor and signal rates, and activity counts.
  <ul>
    <li><strong>Excluded:</strong> the text of any prompt or response</li>
    <li><strong>Excluded:</strong> file names, paths and repository contents</li>
    <li><strong>Excluded:</strong> session titles and any generated summaries</li>
  </ul>
  Every number here is an aggregate over the whole project and cannot be reversed to
  recover an individual prompt.
</div>

<footer>
  <span>Generated by Prompt.ly</span>
  <span>{e(payload['schema'])}</span>
</footer>
</div></body></html>"""


def build(report: dict, anonymize: bool = False, include_benchmark: bool = True) -> dict:
    """Redacted payload plus a rendered HTML document."""
    payload = redacted_payload(report, anonymize=anonymize)
    benchmark = None
    if include_benchmark:
        try:
            b = run_benchmark()
            benchmark = {k: b[k] for k in ("pairs", "pairs_correct", "auc", "ratio")}
        except Exception:
            benchmark = None
    payload["benchmark"] = benchmark
    return {"payload": payload, "html": render_html(payload, benchmark)}


def payload_json(report: dict, anonymize: bool = False) -> str:
    return json.dumps(redacted_payload(report, anonymize=anonymize), indent=2)
