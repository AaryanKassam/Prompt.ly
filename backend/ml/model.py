"""Phase 2 scoring model: an MLP regression head over [embedding | structural].

Architecture (from the handoff doc), generalized to the actual feature widths:

    input = concat(embedding[384], structural_signals[STRUCTURAL_DIM])
          -> Linear(in, 128) -> ReLU -> Dropout(0.2)
          -> Linear(128, 32)  -> ReLU
          -> Linear(32, 1)    -> Sigmoid   (x10 at inference => 0-10 score)

torch is imported lazily so the backend runs without it installed.
"""
from __future__ import annotations

from .embeddings import EMBED_DIM
from .features import STRUCTURAL_DIM

INPUT_DIM = EMBED_DIM + STRUCTURAL_DIM


def build_model(input_dim: int = INPUT_DIM):
    """Construct the MLP. Requires torch (`pip install torch`)."""
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(input_dim, 128),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(128, 32),
        nn.ReLU(),
        nn.Linear(32, 1),
        nn.Sigmoid(),
    )


def predict_scores(model, features):
    """Run the model on an (N, INPUT_DIM) array -> list of 0-10 floats."""
    import torch

    model.eval()
    with torch.no_grad():
        x = torch.as_tensor(features, dtype=torch.float32)
        out = model(x).squeeze(-1) * 10.0
    return out.tolist()
