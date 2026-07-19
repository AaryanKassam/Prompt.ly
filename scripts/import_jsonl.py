"""CLI: import Claude Code sessions from ~/.claude/projects/ into the database.

Usage:
    python scripts/import_jsonl.py                 # import everything
    python scripts/import_jsonl.py --dir PATH      # custom projects dir
    python scripts/import_jsonl.py --dry-run       # parse + report, don't write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script: add the repo root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.ingestion.jsonl_parser import parse_all  # noqa: E402
from backend.ingestion.store import ImportResult, upsert_session  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Import Claude Code JSONL sessions.")
    ap.add_argument("--dir", type=Path, default=None, help="Projects dir (default: ~/.claude/projects)")
    ap.add_argument("--dry-run", action="store_true", help="Parse and report without writing to the DB")
    args = ap.parse_args()

    sessions = list(parse_all(args.dir))
    total_prompts = sum(len(s.prompts) for s in sessions)
    print(f"Parsed {len(sessions)} session(s), {total_prompts} prompt(s).")

    if args.dry_run:
        for s in sessions:
            print(f"  [{s.external_id[:8]}] {s.title or '(untitled)'} — {len(s.prompts)} prompts")
        return 0

    init_db()
    result = ImportResult()
    with SessionLocal() as db:
        for s in sessions:
            upsert_session(db, s, result)
        db.commit()

    print(
        f"Done. sessions: +{result.sessions_created} new, {result.sessions_updated} updated; "
        f"prompts: +{result.prompts_created} new, {result.prompts_scored} scored."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
