# Prompt.ly for VS Code

Shows how effectively you're prompting Claude in the folder you have open, in the sidebar.

![activity bar icon](media/icon.svg)

## What it does

- **Sidebar report** — score, grade, trend, per-factor bars, your top recommendations, and your lowest-scoring prompts for the current workspace folder
- **Status bar** — this project's score, always visible; click to open the panel
- **Score selection** — highlight any text, right-click → *Prompt.ly: Score selected text as a prompt*. Use it to grade a prompt before you send it.
- **Multi-root aware** — follows the file you're editing, so the report re-targets when you switch projects

## Install

The extension shells out to the `promptly` CLI in this repo, so clone the repo first, then:

```bash
ln -s "$PWD/vscode-extension" ~/.vscode/extensions/promptly-1.0.0
```

Reload VS Code (`Cmd+Shift+P` → *Developer: Reload Window*). The Prompt.ly icon appears in the activity bar.

If the CLI isn't found automatically, set `promptly.cliPath` in settings to the absolute path of `scripts/promptly`.

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `promptly.cliPath` | *(auto)* | Path to `scripts/promptly` |
| `promptly.dashboardUrl` | `http://localhost:3000` | Where the web dashboard lives |
| `promptly.showStatusBar` | `true` | Show the score in the status bar |
| `promptly.autoRefreshSeconds` | `120` | Refresh interval while the view is open (0 disables) |

## How it stays in sync

The extension has no scoring logic of its own — it calls `promptly report --json`, the same code path used by the terminal UI and the Claude desktop extension. All three read one SQLite database, so they can never disagree about what a prompt is worth.

Data comes from Claude Code's own session logs in `~/.claude/projects/`, which the CLI imports automatically. Run `promptly install-hook` once and imports happen at the end of every Claude Code session, terminal included.
