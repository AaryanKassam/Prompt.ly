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

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# .env is loaded in backend/__init__.py so every entry point gets it regardless
# of which submodule it imports first.

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


# Columns added after the first release. SQLAlchemy's create_all only creates
# missing *tables*, so additive columns need an explicit ALTER.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("prompts", "kind", "VARCHAR(24)"),
    ("prompts", "project_path", "TEXT"),
    ("playbooks", "data", "JSON"),
    ("playbooks", "prompt_count", "INTEGER"),
    ("prompts", "cache_read_tokens", "INTEGER"),
    ("prompts", "cache_creation_tokens", "INTEGER"),
    ("scores", "efficiency", "FLOAT"),
]


def _apply_additive_migrations() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, ddl_type in _ADDED_COLUMNS:
            if table not in existing_tables:
                continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (no-op if they exist)."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()


def get_session():
    """FastAPI dependency that yields a DB session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
