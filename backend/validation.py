"""Measure whether the scorer actually separates good prompts from bad ones.

Two independent checks, because each answers a different objection:

  * **Benchmark** — 20 hand-written pairs expressing the same request weakly and
    well. Pairing controls for topic, so separation reflects prompt quality
    rather than subject matter. Reports mean scores, the ratio between them, and
    pairwise accuracy (how often the strong version outscores its own weak twin),
    which is the number that actually matters: a ratio can look good while
    individual pairs invert.

  * **Outcome correlation** — on the user's real prompts, does a higher score
    predict a better outcome? Led by a rank correlation, because the outcome
    label is bounded at 10 and most prompts sit on that bound, which pulls a
    linear coefficient well below the relationship actually present. Uses the
    independent outcome signals (repetition, iteration count, clarification,
    diff alignment) as ground truth, so it is not the rubric grading its own
    homework. Both figures carry a confidence interval: on a few hundred
    prompts this number moves by more than a tenth on sample size alone.

Neither uses a language model.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .ingestion.classify import KIND_USER, clean
from .ingestion.signals import compute_outcome_score, detect_iteration_count
from .ml.scorer import score as score_text
from .models import Prompt, Session

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "benchmark.json"


def run_benchmark() -> dict:
    """Score the paired fixture set and report separation."""
    pairs = json.loads(FIXTURE.read_text())["pairs"]

    results = []
    for pair in pairs:
        weak = score_text(pair["weak"]).overall
        strong = score_text(pair["strong"]).overall
        results.append(
            {
                "topic": pair["topic"],
                "weak": round(weak, 2),
                "strong": round(strong, 2),
                "delta": round(strong - weak, 2),
                "correct": strong > weak,
            }
        )

    weak_scores = [r["weak"] for r in results]
    strong_scores = [r["strong"] for r in results]
    mean_weak = sum(weak_scores) / len(weak_scores)
    mean_strong = sum(strong_scores) / len(strong_scores)
    correct = sum(1 for r in results if r["correct"])

    # Rank-based separation: probability a random strong prompt outscores a
    # random weak one (ties count as half). This is the Mann-Whitney U statistic,
    # equivalent to ROC AUC, and unlike a ratio it is scale-free.
    wins = ties = 0
    for s in strong_scores:
        for w in weak_scores:
            if s > w:
                wins += 1
            elif s == w:
                ties += 1
    auc = (wins + 0.5 * ties) / (len(strong_scores) * len(weak_scores))

    return {
        "pairs": len(results),
        "mean_weak": round(mean_weak, 2),
        "mean_strong": round(mean_strong, 2),
        "ratio": round(mean_strong / mean_weak, 2) if mean_weak else None,
        "pairwise_accuracy": round(correct / len(results), 3),
        "pairs_correct": correct,
        "auc": round(auc, 3),
        "results": results,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return None if dx == 0 or dy == 0 else round(num / (dx * dy), 3)


def _ranks(values: list[float]) -> list[float]:
    """Competition-free average ranks, so ties share their midpoint."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mid = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation — the honest statistic for this label.

    The outcome label is bounded at 10 and most prompts sit exactly on that
    bound (no repetition, no retries, no clarifying question is the normal
    case, not the exceptional one). Pearson measures *linear* association and
    is pulled down hard by that pile-up, so on this corpus it reads roughly
    half of the monotonic relationship that is actually there. Spearman only
    cares about ordering, which is all the claim needs: do better-scored
    prompts tend to land better?
    """
    return _pearson(_ranks(xs), _ranks(ys))


def _fisher_ci(r: float | None, n: int) -> list[float] | None:
    """95% interval for a correlation, via the Fisher z transform.

    Reported because the bare coefficient invites over-reading. This figure
    moves by more than a tenth on sample size alone, so a drop between two
    runs is only news if the intervals do not overlap.
    """
    if r is None or n < 4 or abs(r) >= 1.0:
        return None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.96 / math.sqrt(n - 3)
    return [round(math.tanh(z - se), 3), round(math.tanh(z + se), 3)]


def run_outcome_correlation(db: DbSession) -> dict:
    """Does a higher rubric score predict a better real-world outcome?"""
    scores: list[float] = []
    outcomes: list[float] = []

    for session in db.scalars(select(Session)):
        prompts = [
            p for p in session.prompts
            if (p.kind or KIND_USER) == KIND_USER and clean(p.text)
        ]
        for i, p in enumerate(prompts):
            if not (p.score and p.score.overall is not None):
                continue
            nxt = prompts[i + 1] if i + 1 < len(prompts) else None
            outcome = compute_outcome_score(
                prompt_text=clean(p.text),
                next_prompt_text=clean(nxt.text) if nxt else "",
                response_text=p.response_text or "",
                file_diffs=p.file_diffs,
                iteration_count=detect_iteration_count(prompts, i),
            )
            scores.append(p.score.overall)
            outcomes.append(outcome)

    if len(scores) < 3:
        return {"n": len(scores), "correlation": None, "note": "need at least 3 scored prompts"}

    # Split at the median score and compare mean outcomes — more legible than r
    # alone, and it shows the direction of the effect.
    ordered = sorted(zip(scores, outcomes))
    mid = len(ordered) // 2
    low = [o for _, o in ordered[:mid]]
    high = [o for _, o in ordered[-mid:]] if mid else []

    pearson = _pearson(scores, outcomes)
    spearman = _spearman(scores, outcomes)
    at_ceiling = sum(1 for o in outcomes if o >= 10.0) / len(outcomes)

    return {
        "n": len(scores),
        "correlation": pearson,
        "correlation_ci": _fisher_ci(pearson, len(scores)),
        "spearman": spearman,
        "spearman_ci": _fisher_ci(spearman, len(scores)),
        # What share of the label sits on its upper bound. This is the headline
        # caveat on the Pearson figure rather than a footnote: the closer it is
        # to 1, the less a linear coefficient can possibly report.
        "outcome_at_ceiling": round(at_ceiling, 3),
        "mean_outcome_low_half": round(sum(low) / len(low), 2) if low else None,
        "mean_outcome_high_half": round(sum(high) / len(high), 2) if high else None,
    }


def validate(db: DbSession) -> dict:
    return {"benchmark": run_benchmark(), "outcomes": run_outcome_correlation(db)}
