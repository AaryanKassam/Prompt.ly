"""ORM models for Prompt.ly.

Mirrors the schema in the handoff doc, with two portability tweaks so the same
models run on SQLite (dev) and PostgreSQL (prod):
  * UUIDs are stored as strings (uuid4().hex) instead of a Postgres UUID type.
  * JSONB columns use SQLAlchemy's generic JSON type (maps to JSONB on Postgres,
    TEXT-backed JSON on SQLite).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    """One per Claude Code project session or claude.ai conversation."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'browser' | 'claude_code'
    title: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    project_path: Mapped[Optional[str]] = mapped_column(Text)  # Claude Code only
    conv_id: Mapped[Optional[str]] = mapped_column(Text)       # browser only

    # Natural key of the source session, used to avoid duplicate imports.
    # For Claude Code this is the JSONL sessionId; for browser, the conversationId.
    external_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True)

    prompts: Mapped[list["Prompt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Prompt.turn_index"
    )


class Prompt(Base):
    """One per user turn."""

    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_prompt_turn"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[Optional[str]] = mapped_column(Text)          # null if captureText=false
    response_text: Mapped[Optional[str]] = mapped_column(Text)  # Claude's reply (if captured)
    message_id: Mapped[Optional[str]] = mapped_column(String(128))
    model: Mapped[Optional[str]] = mapped_column(String(80))

    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    tool_calls: Mapped[Optional[list]] = mapped_column(JSON)   # array of tool call objects
    file_diffs: Mapped[Optional[dict]] = mapped_column(JSON)   # {edited, created, deleted}
    summary: Mapped[Optional[str]] = mapped_column(Text)        # Phase 4: "what Claude did"

    session: Mapped["Session"] = relationship(back_populates="prompts")
    score: Mapped[Optional["Score"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", uselist=False
    )
    annotation: Mapped[Optional["Annotation"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", uselist=False
    )


class Score(Base):
    """ML output per prompt."""

    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), unique=True, index=True)

    overall: Mapped[Optional[float]] = mapped_column(Float)  # 0-10
    clarity: Mapped[Optional[float]] = mapped_column(Float)
    specificity: Mapped[Optional[float]] = mapped_column(Float)
    context: Mapped[Optional[float]] = mapped_column(Float)
    constraints: Mapped[Optional[float]] = mapped_column(Float)
    scope: Mapped[Optional[float]] = mapped_column(Float)
    examples: Mapped[Optional[float]] = mapped_column(Float)

    model_phase: Mapped[Optional[int]] = mapped_column(Integer)  # 1=rubric, 2=MLP, 3=fine-tuned
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    prompt: Mapped["Prompt"] = relationship(back_populates="score")


class Annotation(Base):
    """User-added notes and tags."""

    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), unique=True, index=True)

    note: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[list]] = mapped_column(JSON)  # list[str]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    prompt: Mapped["Prompt"] = relationship(back_populates="annotation")
