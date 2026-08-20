"""Prompt.ly backend package.

Loading the repo's `.env` happens here, at package import, because it is the one
place guaranteed to run before any submodule. It previously lived in `db.py`,
which meant configuration was only loaded if something happened to import the
database layer — so `backend.llm` on its own saw no API key and reported a
confusing auth error despite `.env` being correctly filled in.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Real environment variables win over the file, so an explicit `export` or a
# value injected by a deployment platform is never clobbered by a stale .env.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
