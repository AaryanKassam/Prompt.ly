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
# `examples` fell from 6% to 3%. It was the worst-performing factor on the
# corpus by a wide margin (mean 0.8/10), and most of that gap was the rubric
# asking the user to paste code the agent could open itself. The factor now
# rewards grounding rather than transcription, and carries the weight its
# remaining evidence supports.
#
# `model_fit` takes 7%: it is the only factor that measures money rather than
# wording, and the spread it detects is real (Opus $5/$25 per MTok against
# Sonnet $2/$10). It is weighted below the validated quality factors because it
# rests on a keyword heuristic for task weight, not on measured outcomes.
#
# Declared in descending weight order: several consumers render factors by
# iterating this dict, and the heaviest factor should be read first.
WEIGHTS: dict[str, float] = {
    "clarity": 0.21,
    "specificity": 0.17,
    "context": 0.16,
    "efficiency": 0.15,
    "constraints": 0.12,
    "scope": 0.09,
    "model_fit": 0.07,
    "examples": 0.03,
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


# A prompt that meets no signal in a factor is still a prompt, not a zero. The
# old linear map (10 x met/total) put a four-signal factor at 2.5 for meeting
# one, which compounded across seven factors into overall scores that clustered
# in the 4-6 band and left almost nothing above 7 — a scale where the top third
# is unreachable measures nothing at the top.
#
# FLOOR is the credit for showing up; CURVE bends the middle upward so partial
# credit accrues faster than linearly. Both ends stay fixed: meeting nothing is
# still the worst score available, and 10 still requires every signal.
#
# Calibrated on the 284-prompt corpus rather than guessed. A floor of 2.0 read
# as generous but pushed the *minimum* observed score to 5.3, which trades an
# unusable top of the scale for an unusable bottom — if nothing can score badly,
# a good score means nothing. At 1.0/0.90 the corpus mean moves 5.19 -> 6.35 and
# still spans 4.6 to 8.1, so both ends of the range stay reachable.
#
# Most of that lift is not from these two constants: the signal fixes alone
# (structured prompts exempt from the length penalties, `examples` rewarding
# grounding instead of transcription) move the mean to 5.74 on their own, and
# they move it for the prompts that deserve it rather than for everything.
FACTOR_FLOOR = 1.0
FACTOR_CURVE = 0.90


def _factor_score(signal_results: dict[str, bool]) -> float:
    if not signal_results:
        return 0.0
    met = sum(1 for v in signal_results.values() if v)
    fraction = met / len(signal_results)
    if fraction <= 0.0:
        return FACTOR_FLOOR
    return FACTOR_FLOOR + (10.0 - FACTOR_FLOOR) * (fraction ** FACTOR_CURVE)


def score_prompt(text: str, model: str | None = None) -> RubricScore:
    """Score a prompt's text against the rubric.

    `model` is the model that answered the turn; it feeds the `model_fit`
    factor only. Omitted (scoring an unsent draft), that factor passes.
    """
    signals = extract_signals(text, model)
    factors = {factor: _factor_score(results) for factor, results in signals.items()}
    overall = sum(factors[f] * WEIGHTS[f] for f in WEIGHTS)
    return RubricScore(overall=overall, factors=factors, signals=signals)
