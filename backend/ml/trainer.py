"""Batch retraining job for the Phase 2 MLP scorer.

Builds a training set from the database:
  * features = concat(text embedding, structural signal vector)
  * label    = outcome_score / 10  (weak label from session sequence signals)

then trains the MLP, reports MAE / R², and saves weights to ml/weights/.

Guarded: refuses to train below MIN_TRAINING_EXAMPLES because a model fit on a
handful of prompts learns noise. Until then the rubric scorer (Phase 1) stands
in. torch / numpy are imported lazily.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..ingestion.signals import compute_outcome_score, detect_iteration_count
from ..models import Prompt, Session
from .features import signal_vector

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
MIN_TRAINING_EXAMPLES = 50


@dataclass
class TrainingExample:
    text: str
    label: float  # 0..1 (outcome_score / 10)
    structural: list[float]


def build_dataset(db: DbSession) -> list[TrainingExample]:
    """Assemble weak-labeled training examples from all sessions with text."""
    examples: list[TrainingExample] = []
    for session in db.scalars(select(Session)):
        prompts: list[Prompt] = list(session.prompts)  # ordered by turn_index
        for i, p in enumerate(prompts):
            if not p.text:
                continue
            nxt = prompts[i + 1] if i + 1 < len(prompts) else None
            iteration_count = detect_iteration_count(prompts, i)
            outcome = compute_outcome_score(
                prompt_text=p.text,
                next_prompt_text=(nxt.text if nxt else "") or "",
                response_text=p.response_text or "",
                file_diffs=p.file_diffs,
                iteration_count=iteration_count,
            )
            examples.append(
                TrainingExample(text=p.text, label=outcome / 10.0, structural=signal_vector(p.text))
            )
    return examples


def _next_version() -> int:
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    versions = [
        int(p.stem.split("_v")[-1])
        for p in WEIGHTS_DIR.glob("model_v*.pt")
        if p.stem.split("_v")[-1].isdigit()
    ]
    return (max(versions) + 1) if versions else 1


def train(db: DbSession, epochs: int = 200, seed: int = 42) -> dict:
    """Train the MLP on the current DB contents. Returns a metrics dict."""
    examples = build_dataset(db)
    n = len(examples)
    if n < MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": f"need >= {MIN_TRAINING_EXAMPLES} labeled prompts, have {n}",
            "examples": n,
        }

    # Lazy heavy imports.
    import numpy as np
    import torch
    from torch import nn

    from .embeddings import embed
    from .model import build_model

    torch.manual_seed(seed)
    np.random.seed(seed)

    emb = embed([e.text for e in examples])                       # (N, 384)
    struct = np.array([e.structural for e in examples], dtype=np.float32)  # (N, S)
    X = np.concatenate([emb, struct], axis=1).astype(np.float32)
    y = np.array([e.label for e in examples], dtype=np.float32).reshape(-1, 1)

    # 80/20 train/val split.
    idx = np.random.permutation(n)
    split = int(n * 0.8)
    tr, va = idx[:split], idx[split:]
    Xtr, ytr = torch.tensor(X[tr]), torch.tensor(y[tr])
    Xva, yva = torch.tensor(X[va]), torch.tensor(y[va])

    model = build_model(input_dim=X.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    for _ in range(epochs):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(Xtr), ytr)
        loss.backward()
        opt.step()

    # Validation metrics (on the 0-10 scale).
    model.eval()
    with torch.no_grad():
        pred = model(Xva).numpy().reshape(-1) * 10.0
    actual = (y[va].reshape(-1)) * 10.0
    mae = float(np.mean(np.abs(pred - actual)))
    ss_res = float(np.sum((actual - pred) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2)) or 1e-9
    r2 = 1.0 - ss_res / ss_tot

    version = _next_version()
    weights_path = WEIGHTS_DIR / f"model_v{version}.pt"
    torch.save(model.state_dict(), weights_path)
    meta = {
        "version": version,
        "input_dim": int(X.shape[1]),
        "examples": n,
        "train_size": int(split),
        "val_size": int(n - split),
        "mae": round(mae, 3),
        "r2": round(r2, 3),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    (WEIGHTS_DIR / f"model_v{version}.json").write_text(json.dumps(meta, indent=2))

    return {"trained": True, "weights": str(weights_path), **meta}
