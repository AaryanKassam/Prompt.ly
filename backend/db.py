"""Database setup for Prompt.ly.

Uses SQLAlchemy 2.0 with a sync engine. The database is chosen via the
DATABASE_URL environment variable so we can develop on zero-setup SQLite now
and switch to PostgreSQL (Phase 3) by only changing that one variable:

    # default, no setup required
    DATABASE_URL=sqlite:///promptly.db

    # production
    DATABASE_URL=postgresql+psycopg2://promptly:promptly@localhost:5432/promptly
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# Default to a SQLite file living at the repo root (backend/../promptly.db).
_DEFAULT_SQLITE = f"sqlite:///{Path(__file__).resolve().parent.parent / 'promptly.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)

# check_same_thread is a SQLite-only flag needed when the same connection is
# touched from FastAPI's threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (no-op if they exist)."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI dependency that yields a DB session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
