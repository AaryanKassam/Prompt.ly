"""Prompt.ly FastAPI application entrypoint.

Run locally (from the repo root):
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import ingest

app = FastAPI(title="Prompt.ly API", version="0.1.0")

# The Chrome extension and the Next.js dashboard both call this API from other
# origins, so allow cross-origin requests during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
