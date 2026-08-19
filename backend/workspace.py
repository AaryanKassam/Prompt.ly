"""Detect which folder is currently open in VS Code (and friends).

VS Code keeps one directory per window under ``workspaceStorage/<hash>/``, each
containing a ``workspace.json`` that names the folder that window has open. The
directory's mtime is bumped while that window is in use, so sorting by mtime
gives "most recently active workspace first" — which is what we want when the
user asks Prompt.ly for a report without naming a path.

No VS Code extension or IPC is required; this is read-only inspection of files
the editor already maintains. Cursor and VSCodium use the same layout under
different application-support directories, so they're checked too.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

# (label, path to the User/ directory) for every editor we know about.
def _candidate_roots() -> list[tuple[str, Path]]:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        return [
            ("VS Code", base / "Code" / "User"),
            ("VS Code Insiders", base / "Code - Insiders" / "User"),
            ("Cursor", base / "Cursor" / "User"),
            ("VSCodium", base / "VSCodium" / "User"),
            ("Windsurf", base / "Windsurf" / "User"),
        ]
    if sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return [
            ("VS Code", base / "Code" / "User"),
            ("Cursor", base / "Cursor" / "User"),
            ("VSCodium", base / "VSCodium" / "User"),
        ]
    base = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
    return [
        ("VS Code", base / "Code" / "User"),
        ("Cursor", base / "Cursor" / "User"),
        ("VSCodium", base / "VSCodium" / "User"),
    ]


@dataclass
class OpenWorkspace:
    path: str          # absolute folder path
    editor: str        # "VS Code", "Cursor", …
    last_active: float # mtime epoch seconds — higher is more recent

    def as_dict(self) -> dict:
        return {"path": self.path, "editor": self.editor, "last_active": self.last_active}


def _folder_from_workspace_json(entry: Path) -> str | None:
    """Read one workspaceStorage/<hash>/workspace.json and return its folder path."""
    try:
        data = json.loads((entry / "workspace.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    # Single-folder windows use "folder"; .code-workspace files use "workspace".
    uri = data.get("folder") or data.get("workspace")
    if not isinstance(uri, str) or not uri.startswith("file://"):
        return None
    path = unquote(urlparse(uri).path)
    # A .code-workspace file points at the file, not the directory it describes.
    if path.endswith(".code-workspace"):
        path = str(Path(path).parent)
    return path or None


def list_open_workspaces(limit: int = 20) -> list[OpenWorkspace]:
    """All editor workspaces on this machine, most recently active first.

    Folders that no longer exist on disk are skipped, and a folder open in more
    than one editor is reported once, under whichever was touched most recently.
    """
    found: dict[str, OpenWorkspace] = {}
    for editor, user_dir in _candidate_roots():
        storage = user_dir / "workspaceStorage"
        if not storage.is_dir():
            continue
        try:
            entries = [e for e in storage.iterdir() if e.is_dir()]
        except OSError:
            continue
        for entry in entries:
            path = _folder_from_workspace_json(entry)
            if not path or not Path(path).is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            prev = found.get(path)
            if prev is None or mtime > prev.last_active:
                found[path] = OpenWorkspace(path=path, editor=editor, last_active=mtime)

    ordered = sorted(found.values(), key=lambda w: w.last_active, reverse=True)
    return ordered[:limit]


def detect_active_workspace() -> OpenWorkspace | None:
    """Best guess at the folder the user is looking at right now.

    Preference order:
      1. PROMPTLY_WORKSPACE — explicit override, always wins.
      2. The most recently active editor workspace. This is the only signal that
         actually tracks the user switching windows, so it outranks the process's
         own working directory — otherwise the dashboard would permanently
         report on whichever folder `uvicorn` happened to be started from.
      3. The current working directory, if it looks like a project root. Reached
         when no editor is installed, or when launched somewhere the editor
         doesn't know about.
    """
    override = os.getenv("PROMPTLY_WORKSPACE")
    if override and Path(override).is_dir():
        return OpenWorkspace(
            path=str(Path(override).resolve()), editor="override", last_active=0.0
        )

    workspaces = list_open_workspaces(limit=1)
    if workspaces:
        return workspaces[0]

    cwd = Path.cwd()
    if cwd != Path.home() and _looks_like_project_root(cwd):
        return OpenWorkspace(path=str(cwd), editor="working directory", last_active=0.0)
    return None


_PROJECT_MARKERS = (
    ".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "requirements.txt", "setup.py", "pom.xml", "build.gradle", "Gemfile",
)


def _looks_like_project_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in _PROJECT_MARKERS)
