"""Work out which project a prompt actually belongs to.

Claude Code records a session's `cwd`, and until now that was the only thing
deciding which project a prompt counted towards. That is wrong whenever someone
starts Claude in one repo and works on another — on this machine it filed
HealthLink and claude-arcade work under prompt.ly, skewing both projects'
scores.

The files a turn actually touched are far better evidence than the directory the
process happened to start in, so attribution walks up from each edited file to
its enclosing repository root and takes the majority.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

# Weaker markers, consulted only when nothing up the tree is a git repository.
_MANIFEST_MARKERS = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")

# Directories that are never a meaningful project root on their own.
_TOO_SHALLOW = {"/", "/Users", "/home", "/tmp", "/var", "/opt"}


@lru_cache(maxsize=4096)
def repo_root_for(path: str) -> str | None:
    """Nearest ancestor of `path` that looks like a project root.

    `.git` wins over every other marker and is checked in its own pass, because
    sub-packages carry their own manifests: `frontend/package.json` would
    otherwise make the dashboard its own "project" instead of part of the repo
    that contains it. Only when no ancestor is a git repository do the weaker
    manifest markers decide.
    """
    try:
        parents = list(Path(path).parents)
    except (ValueError, OSError):
        return None

    def scan(markers: tuple[str, ...]) -> str | None:
        for parent in parents:
            candidate = str(parent)
            if candidate in _TOO_SHALLOW:
                return None
            try:
                if any((parent / m).exists() for m in markers):
                    return candidate
            except OSError:
                continue
        return None

    return scan((".git",)) or scan(_MANIFEST_MARKERS)


def paths_touched(tool_calls: list | None, file_diffs: dict | None) -> list[str]:
    """Every filesystem path a turn read or wrote."""
    found: list[str] = []
    for bucket in ("created", "edited", "deleted"):
        found.extend((file_diffs or {}).get(bucket) or [])
    for call in tool_calls or []:
        value = (call.get("input") or {}).get("file_path")
        if isinstance(value, str):
            found.append(value)
    return [p for p in found if p.startswith("/")]


def attribute_prompt(
    tool_calls: list | None,
    file_diffs: dict | None,
    fallback: str | None,
) -> str | None:
    """Project this turn belongs to, by majority of the files it touched.

    Falls back to the session's working directory when a turn touched no files
    (a question, a plan, a refusal) — those genuinely belong wherever the user
    was standing.
    """
    roots = [r for r in (repo_root_for(p) for p in paths_touched(tool_calls, file_diffs)) if r]
    if not roots:
        return fallback

    root, count = Counter(roots).most_common(1)[0]
    # A clear majority avoids reassigning a turn that merely glanced at one file
    # in another repo.
    return root if count / len(roots) >= 0.6 else fallback
