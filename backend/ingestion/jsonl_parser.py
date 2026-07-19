"""Parse Claude Code session logs from ``~/.claude/projects/``.

Each project directory contains one ``.jsonl`` file per session. Every line is a
JSON record; the ones we care about:

  * ``type: "user"``    -> a real user prompt when ``message.content`` is a string.
                           When content is a list of ``tool_result`` blocks it is
                           an intermediate tool result, not a new turn.
  * ``type: "assistant"`` -> Claude's reply: ``message.content`` holds ``text`` and
                             ``tool_use`` blocks; ``message.usage`` holds tokens.
  * ``type: "ai-title"``  -> a generated title for the session.

We reduce the flat record stream into a list of *turns*. A turn begins at a user
prompt and absorbs every assistant text block, tool call, and token count until
the next user prompt.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

# Tool calls that mutate files, used to reconstruct diffs.
_WRITE_TOOLS = {"Write"}
_EDIT_TOOLS = {"Edit", "MultiEdit"}


def default_projects_dir() -> Path:
    """Location of Claude Code session logs (override with CLAUDE_PROJECTS_DIR)."""
    return Path(os.getenv("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))


@dataclass
class ParsedPrompt:
    turn_index: int
    text: str
    response_text: str = ""
    message_id: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: Optional[datetime] = None
    tool_calls: list = field(default_factory=list)  # [{name, input}]

    def file_diffs(self) -> dict:
        """Reconstruct which files were created/edited from this turn's tool calls."""
        created: list[str] = []
        edited: list[str] = []
        for call in self.tool_calls:
            name = call.get("name")
            path = (call.get("input") or {}).get("file_path")
            if not path:
                continue
            if name in _WRITE_TOOLS and path not in created:
                created.append(path)
            elif name in _EDIT_TOOLS and path not in edited:
                edited.append(path)
        return {"created": created, "edited": edited, "deleted": []}


@dataclass
class ParsedSession:
    external_id: str          # JSONL sessionId
    source: str = "claude_code"
    title: Optional[str] = None
    project_path: Optional[str] = None
    created_at: Optional[datetime] = None
    prompts: list[ParsedPrompt] = field(default_factory=list)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # JSONL timestamps are ISO-8601 with a trailing "Z".
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_user_prompt(rec: dict) -> Optional[str]:
    """Return the prompt text if ``rec`` is a genuine typed user prompt, else None."""
    if rec.get("type") != "user" or rec.get("isSidechain"):
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str) and content.strip():
        return content
    # A list content is either tool_result blocks (skip) or text blocks (rare).
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        joined = "\n".join(t for t in texts if t).strip()
        return joined or None
    return None


def parse_file(path: Path) -> Optional[ParsedSession]:
    """Parse a single session ``.jsonl`` file into a ParsedSession."""
    session: Optional[ParsedSession] = None
    current: Optional[ParsedPrompt] = None
    turn_index = 0

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = rec.get("type")

            # Lazily create the session from the first record that carries metadata.
            if session is None and rec.get("sessionId"):
                session = ParsedSession(
                    external_id=rec["sessionId"],
                    project_path=rec.get("cwd"),
                    created_at=_parse_ts(rec.get("timestamp")),
                )
            elif session is not None:
                # Backfill fields that early records (e.g. queue-operation) omit.
                if session.project_path is None and rec.get("cwd"):
                    session.project_path = rec["cwd"]
                if session.created_at is None:
                    session.created_at = _parse_ts(rec.get("timestamp"))

            if rtype == "ai-title" and session is not None:
                session.title = rec.get("aiTitle") or session.title
                continue

            # New user prompt -> flush the previous turn and start a fresh one.
            prompt_text = _is_user_prompt(rec)
            if prompt_text is not None:
                if current is not None and session is not None:
                    session.prompts.append(current)
                turn_index += 1
                current = ParsedPrompt(
                    turn_index=turn_index,
                    text=prompt_text,
                    timestamp=_parse_ts(rec.get("timestamp")),
                )
                continue

            # Assistant activity accrues to the current turn.
            if rtype == "assistant" and current is not None and not rec.get("isSidechain"):
                msg = rec.get("message") or {}
                if current.message_id is None:
                    current.message_id = msg.get("id")
                current.model = msg.get("model") or current.model
                usage = msg.get("usage") or {}
                current.output_tokens += int(usage.get("output_tokens") or 0)
                # input_tokens reflects the prompt's context size; keep the largest seen.
                current.input_tokens = max(current.input_tokens, int(usage.get("input_tokens") or 0))
                for block in msg.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        current.response_text += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        current.tool_calls.append(
                            {"name": block.get("name"), "input": block.get("input", {})}
                        )

    if current is not None and session is not None:
        session.prompts.append(current)

    return session


def iter_session_files(base: Optional[Path] = None) -> Iterator[Path]:
    """Yield every session ``.jsonl`` file under the projects directory."""
    base = base or default_projects_dir()
    if not base.exists():
        return
    yield from sorted(base.glob("*/*.jsonl"))


def parse_all(base: Optional[Path] = None) -> Iterator[ParsedSession]:
    """Parse every session file, skipping any that yield no prompts."""
    for path in iter_session_files(base):
        parsed = parse_file(path)
        if parsed and parsed.prompts:
            yield parsed
