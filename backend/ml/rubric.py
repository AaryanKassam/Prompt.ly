"""Phase 1 rule-based rubric scorer.

Turns the boolean signals from ``features.extract_signals`` into a 0-10 score per
factor (fraction of signals met x 10) and a weighted overall score. This ships on
day 1 with no training data; Phase 2's MLP later blends with or replaces it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .features import extract_signals

# Factor weights (must sum to 1.0). Sourced from the handoff rubric.
WEIGHTS: dict[str, float] = {
    "clarity": 0.25,
    "specificity": 0.20,
    "context": 0.20,
    "constraints": 0.15,
    "scope": 0.10,
    "examples": 0.10,
}

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
