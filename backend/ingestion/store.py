"""Persist parsed sessions into the database (idempotent upserts)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..ml.rubric import score_prompt
from ..models import Prompt, Score, Session
from .jsonl_parser import ParsedSession


@dataclass
class ImportResult:
    sessions_created: int = 0
    sessions_updated: int = 0
    prompts_created: int = 0
    prompts_scored: int = 0


def score_and_attach(db: DbSession, prompt: Prompt) -> Score:
    """Run the rubric scorer on a prompt and attach a Score row (replacing any)."""
    result = score_prompt(prompt.text or "")
    if prompt.score is not None:
        db.delete(prompt.score)
        db.flush()
    score = Score(**result.as_score_kwargs())
    prompt.score = score  # set the relationship so it's consistent in-session
    db.add(score)
    return score


def upsert_session(db: DbSession, parsed: ParsedSession, result: ImportResult) -> None:
    """Insert or update one session and its prompts, keyed on external_id.

    Re-importing an existing session adds only prompts whose turn_index is new,
    so running the importer repeatedly is safe.
    """
    session = db.scalar(select(Session).where(Session.external_id == parsed.external_id))
    if session is None:
        session = Session(
            source=parsed.source,
            title=parsed.title,
            created_at=parsed.created_at,
            project_path=parsed.project_path,
            external_id=parsed.external_id,
        )
        db.add(session)
        db.flush()  # assign session.id before adding prompts
        result.sessions_created += 1
    else:
        # Refresh mutable metadata (title/path are filled in after the first turns).
        session.title = parsed.title or session.title
        session.project_path = session.project_path or parsed.project_path
        session.created_at = session.created_at or parsed.created_at
        result.sessions_updated += 1

    existing_turns = {
        row[0] for row in db.execute(
            select(Prompt.turn_index).where(Prompt.session_id == session.id)
        )
    }

    for p in parsed.prompts:
        if p.turn_index in existing_turns:
            continue
        prompt = Prompt(
            session_id=session.id,
            turn_index=p.turn_index,
            text=p.text,
            response_text=p.response_text or None,
            message_id=p.message_id,
            model=p.model,
            input_tokens=p.input_tokens or None,
            output_tokens=p.output_tokens or None,
            timestamp=p.timestamp,
            tool_calls=p.tool_calls or None,
            file_diffs=p.file_diffs(),
        )
        db.add(prompt)
        db.flush()  # assign prompt.id before scoring
        score_and_attach(db, prompt)
        result.prompts_created += 1
        result.prompts_scored += 1
