"""Unified scoring entrypoint that blends the Phase 2 MLP with the Phase 1 rubric.

Policy (from the handoff doc):
  * Always compute the rubric — it provides the per-factor breakdown the UI shows.
  * If a trained MLP exists AND was trained on >= BLEND_MIN_EXAMPLES examples,
    blend the overall score (70% MLP, 30% rubric) and mark it model_phase=2.
  * Otherwise use the rubric alone (model_phase=1).

The MLP only predicts the *overall* score; factor sub-scores always come from the
rubric. Everything degrades gracefully: missing weights, too little data, or
missing torch all fall back to the rubric with no error.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .features import signal_vector
from .rubric import RubricScore, score_prompt

BLEND_MIN_EXAMPLES = 200  # MLP only trusted once trained on this many prompts
MLP_WEIGHT = 0.7


def _latest_meta_path() -> Path | None:
    from .trainer import WEIGHTS_DIR

    metas = [p for p in WEIGHTS_DIR.glob("model_v*.json")]
    if not metas:
        return None
    return max(metas, key=lambda p: int(p.stem.split("_v")[-1]))


@lru_cache(maxsize=1)
def _load_active_model():
    """Return (model, meta) if a trustworthy trained model exists, else None."""
    meta_path = _latest_meta_path()
    if meta_path is None:
        return None
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if meta.get("examples", 0) < BLEND_MIN_EXAMPLES:
        return None
    try:
        import torch

        from .model import build_model

        model = build_model(input_dim=meta["input_dim"])
        model.load_state_dict(torch.load(meta_path.with_suffix(".pt"), map_location="cpu"))
        model.eval()
        return (model, meta)
    except Exception:
        return None


def reset_model_cache() -> None:
    """Call after (re)training so the next score picks up new weights."""
    _load_active_model.cache_clear()


def active_model_info() -> dict | None:
    """Metadata about the currently active MLP, or None if rubric-only."""
    active = _load_active_model()
    return active[1] if active else None


def score(text: str) -> RubricScore:
    """Score a prompt, blending the MLP in when available."""
    rubric = score_prompt(text)
    active = _load_active_model()
    if not active or not (text or "").strip():
        return rubric

    model, _meta = active
    try:
        import numpy as np

        from .embeddings import embed_one
        from .model import predict_scores

        feat = np.concatenate(
            [embed_one(text), np.array(signal_vector(text), dtype="float32")]
        ).reshape(1, -1)
        mlp_overall = predict_scores(model, feat)[0]
        blended = MLP_WEIGHT * mlp_overall + (1 - MLP_WEIGHT) * rubric.overall
        rubric.overall = max(0.0, min(10.0, blended))
        rubric.model_phase = 2
    except Exception:
        # Any failure -> keep the rubric result unchanged.
        pass
    return rubric
