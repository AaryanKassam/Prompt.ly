"""CLI: retrain the Phase 2 MLP scorer on current DB contents.

Usage:
    python scripts/retrain.py            # train (needs >= 50 labeled prompts)
    python scripts/retrain.py --status   # show dataset size without training

Requires the optional ML deps: pip install sentence-transformers torch numpy
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.ml.trainer import build_dataset, train  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Retrain the Prompt.ly MLP scorer.")
    ap.add_argument("--status", action="store_true", help="Report dataset size, don't train")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        if args.status:
            n = len(build_dataset(db))
            print(f"{n} labeled training example(s) available.")
            return 0
        result = train(db)

    if not result.get("trained"):
        print(f"Not trained: {result.get('reason')}")
        return 0
    print(
        f"Trained model v{result['version']} on {result['examples']} examples "
        f"— MAE {result['mae']}, R² {result['r2']}\nWeights: {result['weights']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
