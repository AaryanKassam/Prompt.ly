#!/usr/bin/env python3
"""Register the Prompt.ly MCP server with the Claude desktop app and Claude Code.

Both clients launch MCP servers as subprocesses described by a JSON config, so
"installing" means adding one entry pointing at ``server.py`` and the Python
interpreter that has Prompt.ly's dependencies (the repo venv).

Safe to re-run: the existing config is backed up and only the ``promptly`` key
is touched. Pass --uninstall to remove it again.

    python mcp_server/install.py
    python mcp_server/install.py --uninstall
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "mcp_server" / "server.py"
KEY = "promptly"


def desktop_config_path() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform.startswith("win"):
        import os

        return Path(os.getenv("APPDATA", home)) / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def python_interpreter() -> str:
    """Prefer the repo venv — the Claude app's PATH won't have our dependencies."""
    venv = REPO_ROOT / "backend" / "venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    venv_win = REPO_ROOT / "backend" / "venv" / "Scripts" / "python.exe"
    if venv_win.exists():
        return str(venv_win)
    return sys.executable


def server_entry() -> dict:
    return {
        "command": python_interpreter(),
        "args": [str(SERVER)],
        "env": {"PYTHONPATH": str(REPO_ROOT)},
    }


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        print(f"  ! {path} is not valid JSON — leaving it alone.")
        raise SystemExit(1)


def _backup(path: Path) -> None:
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = path.with_suffix(f".backup-{stamp}.json")
        shutil.copy(path, dest)
        print(f"  backed up -> {dest.name}")


def update(path: Path, label: str, uninstall: bool) -> None:
    config = _load(path)
    servers = config.setdefault("mcpServers", {})

    if uninstall:
        if servers.pop(KEY, None) is None:
            print(f"  {label}: not installed, nothing to do.")
            return
    else:
        servers[KEY] = server_entry()

    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"  {label}: {'removed' if uninstall else 'installed'} -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true", help="remove the entry instead")
    parser.add_argument(
        "--desktop-only", action="store_true", help="skip the Claude Code project config"
    )
    args = parser.parse_args()

    if not SERVER.exists():
        raise SystemExit(f"server.py not found at {SERVER}")

    print("Prompt.ly MCP server")
    print(f"  interpreter: {python_interpreter()}")
    print(f"  entry point: {SERVER}\n")

    update(desktop_config_path(), "Claude desktop app", args.uninstall)
    if not args.desktop_only:
        update(REPO_ROOT / ".mcp.json", "Claude Code (this repo)", args.uninstall)

    if not args.uninstall:
        print("\nRestart the Claude desktop app, then ask: \"what's my prompt report?\"")


if __name__ == "__main__":
    main()
