"""Phase 1 rule-based rubric scorer.

Turns the boolean signals from ``features.extract_signals`` into a 0-10 score per
factor (fraction of signals met x 10) and a weighted overall score. This ships on
day 1 with no training data; Phase 2's MLP later blends with or replaces it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .features import extract_signals

# Factor weights (must sum to 1.0). The first six come from the handoff rubric;
# `efficiency` was added to score what a prompt *costs*, not just how good it is,
# and every other weight was scaled down proportionally to make room for it.
#
# 15% is a deliberate compromise. Only one of efficiency's four signals is
# statistically separated on the corpus measured so far (see features.py), so
# weighting it above the validated quality factors would overstate the evidence;
# weighting it lower would not change any ranking. Override with the
# PROMPTLY_EFFICIENCY_WEIGHT env var to explore a different balance.
# Declared in descending weight order: several consumers render factors by
# iterating this dict, and the heaviest factor should be read first.
WEIGHTS: dict[str, float] = {
    "clarity": 0.22,
    "specificity": 0.18,
    "context": 0.17,
    "efficiency": 0.15,
    "constraints": 0.13,
    "scope": 0.09,
    "examples": 0.06,
}


def _apply_weight_override() -> None:
    """Let PROMPTLY_EFFICIENCY_WEIGHT retune efficiency vs. the quality factors.

    The other six keep their relative proportions and absorb the difference, so
    the weights still sum to 1.0 whatever value is set.
    """
    import os

    raw = os.getenv("PROMPTLY_EFFICIENCY_WEIGHT")
    if raw is None:
        return
    try:
        target = float(raw)
    except ValueError:
        return
    if not 0.0 <= target < 1.0:
        return
    others = {k: v for k, v in WEIGHTS.items() if k != "efficiency"}
    scale = (1.0 - target) / sum(others.values())
    for key, value in others.items():
        WEIGHTS[key] = round(value * scale, 6)
    WEIGHTS["efficiency"] = target


_apply_weight_override()

MODEL_PHASE = 1  # 1 = rubric, 2 = MLP, 3 = fine-tuned


@dataclass
class RubricScore:
    overall: float
    factors: dict[str, float] = field(default_factory=dict)          # factor -> 0-10
    signals: dict[str, dict[str, bool]] = field(default_factory=dict)  # factor -> signal -> bool
    model_phase: int = MODEL_PHASE

    def as_score_kwargs(self) -> dict:
        """Fields for constructing a models.Score row."""
        return {
            "overall": round(self.overall, 2),
            "model_phase": self.model_phase,
            **{f: round(v, 2) for f, v in self.factors.items()},
        }


def _factor_score(signal_results: dict[str, bool]) -> float:
    if not signal_results:
        return 0.0
    met = sum(1 for v in signal_results.values() if v)
    return 10.0 * met / len(signal_results)


def score_prompt(text: str) -> RubricScore:
    """Score a prompt's text against the rubric."""
    signals = extract_signals(text)
    factors = {factor: _factor_score(results) for factor, results in signals.items()}
    overall = sum(factors[f] * WEIGHTS[f] for f in WEIGHTS)
    return RubricScore(overall=overall, factors=factors, signals=signals)
