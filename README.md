# prompt.ly

Scores how effectively you prompt Claude, per project — then shows you how to improve.

Prompt.ly reads the Claude Code session logs already on your machine, grades every prompt 0–10 across six quality factors, and reports how you're doing in whichever project you're working on. It runs entirely locally.

![Prompt.ly dashboard](docs/dashboard.png)

---

## Why

Everyone using an AI coding assistant is writing dozens of prompts a day, and nobody gets feedback on any of them. A vague prompt costs a search, a wrong guess, and a round trip — but that cost is invisible, so the habit never changes.

Prompt.ly makes it visible. It found that 96% of my prompts never paste the actual error, and 88% never name a file.

---

## Four ways to use it

All four read the same database and call the same scoring engine, so they can never disagree about what a prompt is worth.

| Surface | Best for |
|---|---|
| **Terminal** | Scoring a draft *before* you send it; cwd-aware reports |
| **VS Code** | A sidebar score for the project you're in, while you work |
| **Claude app** | Asking "how's my prompting?" in conversation |
| **Dashboard** | Deep dives, expandable factors, the playbook, sharing |

---

## Install

Requires Python 3.10+ and Claude Code.

```bash
git clone https://github.com/AaryanKassam/Prompt.ly.git
cd Prompt.ly

python3 -m venv backend/venv
backend/venv/bin/pip install fastapi uvicorn sqlalchemy python-dotenv rich

backend/venv/bin/python scripts/import_jsonl.py    # import your history
```

That's the whole setup. Your existing Claude Code sessions are now scored.

Two optional extras, each only needed for one thing:

```bash
backend/venv/bin/pip install anthropic                     # prompt rewrites + playbook
backend/venv/bin/pip install "mcp[cli]"                    # Claude desktop extension
backend/venv/bin/pip install torch sentence-transformers   # training the MLP
```

### Terminal

```bash
ln -s "$PWD/scripts/promptly" ~/.local/bin/promptly   # put it on your PATH
promptly install-hook                                 # auto-import after each session
promptly                                              # see every command
```

`install-hook` registers a Claude Code `SessionEnd` hook, so new sessions import themselves and there's nothing to remember to run.

**Score a prompt before you send it** — the thing only the terminal can do:

```bash
promptly score "fix the parser"    # inline
promptly score -c                  # score whatever you just copied
promptly score -e                  # compose in $EDITOR
cat draft.txt | promptly score     # from a file
```

Then the rest:

| Command | Short | What |
|---|---|---|
| `promptly report [path]` | `r` | Report for a folder, defaulting to the current one |
| `promptly projects` | `p` | Every tracked folder |
| `promptly watch` | `w` | Live report, refreshes as you work |
| `promptly share` | | Redacted report safe to send to someone else |
| `promptly doctor` | `check` | Check the setup and print the fix for anything broken |
| `promptly sync` | | Import new sessions now |

The launcher re-execs under the repo venv, so it works from any directory regardless of which Python is active.

### VS Code

```bash
ln -s "$PWD/vscode-extension" ~/.vscode/extensions/promptly-1.0.0
```

Reload the window (`Cmd+Shift+P` → *Developer: Reload Window*). The Prompt.ly icon appears in the activity bar.

- **Sidebar** — score, trend, factor bars, recommendations, worst prompts for the folder you have open
- **Status bar** — this project's score, always visible
- **Right-click any selection** → *Prompt.ly: Score selected text as a prompt*
- Multi-root aware: re-targets when you switch between projects

It holds no scoring logic — it shells out to `promptly report --json`. If the CLI isn't found automatically, set `promptly.cliPath` in settings to the absolute path of `scripts/promptly`.

### Dashboard

```bash
./scripts/dev            # starts both servers
```

Open **http://localhost:3000**. `./scripts/dev stop` shuts them down.

### Claude app extension

```bash
backend/venv/bin/python mcp_server/install.py
```

Restart the Claude desktop app, then ask *"what's my prompt report?"*. It auto-detects the folder open in your editor. Five tools: `prompt_report`, `score_draft_prompt`, `detect_workspace`, `list_tracked_projects`, `refresh_data`.

### Chrome extension (optional)

Only needed to capture claude.ai — Claude Code is covered by the log parser. See [`extension/README.md`](extension/README.md).

---

## How scoring works

Every prompt is graded 0–10 across six weighted factors, built from 19 structural signals:

| Factor | Weight | Measures |
|---|---|---|
| Clarity | 25% | One unambiguous action, active voice, no hedging |
| Specificity | 20% | Names files, identifiers, expected output shape |
| Context | 20% | Background, intent, relevant stack |
| Constraints | 15% | What not to change, where to stop |
| Scope | 10% | One task per request, sized to be reviewable |
| Examples | 10% | Code, errors, or a concrete input/output case |

**The scorer is deterministic and runs offline.** No language model is involved in producing a score — that's the point. A rubric you own is defensible; a wrapper around someone else's judgement isn't.

### Does it actually work?

`promptly validate` measures it against a benchmark of 20 hand-written pairs, each expressing the same request once weakly and once well. Pairing controls for topic, so the result reflects prompt quality rather than subject matter.

| Metric | Result |
|---|---|
| Weak mean | 3.48 / 10 |
| Strong mean | 6.02 / 10 |
| **Pairwise accuracy** | **20 / 20** |
| **AUC** | **0.981** |

It also correlates scores against independent outcome signals (repetition, iteration count, clarification requests, diff alignment) on real prompts — so the rubric isn't grading its own homework.

---

## Where a language model *is* used

Two optional features, both garnish over numbers measured locally first:

- **Rewrite this prompt** — a full rewrite of one weak prompt
- **Playbook** — turns your measured weaknesses into a personalised guide with your own prompts rewritten

Both need an API key. Everything else works without one.

```bash
cp .env.example .env      # then paste your key into ANTHROPIC_API_KEY
./scripts/dev             # restart to pick it up
```

Rewrites return an **assumptions list** naming anything the model invented — a file path, a rationale — so it's never presented as fact you can rely on.

---

## Sharing a report

The dashboard shows your prompt text, file paths and session titles. None of that can go to an employer.

```bash
promptly share              # ./promptly-report-<project>.html
promptly share --anonymize  # ...with the folder name hidden
```

<img src="docs/shareable-report.png" alt="Shareable report" width="480">

The file carries aggregate scores, factor breakdowns, all 19 habit rates, activity counts and the benchmark result. It contains **no prompt text, no file paths, no session titles**. Redaction is a whitelist, so a field added to the internal report later cannot leak into a shared file by default.

---

## Privacy

Everything runs on your machine. There is no server, no account, and no telemetry.

- Prompt data comes from `~/.claude/projects/`, which Claude Code already writes
- The database is a local SQLite file at the repo root
- The Chrome extension talks only to `localhost`, and text capture is off until you turn it on
- The only outbound network call is to the Anthropic API, only for the two optional features above, and only if you configure a key

---

## Architecture

```
prompt.ly/
├── backend/              FastAPI + SQLAlchemy
│   ├── cli.py            The `promptly` terminal UI
│   ├── reports.py        Per-project report engine + cache
│   ├── share.py          Redacted shareable report
│   ├── validation.py     Benchmark + outcome correlation
│   ├── workspace.py      Detects the folder open in VS Code / Cursor
│   ├── llm.py            The only language-model calls in the project
│   ├── ingestion/        JSONL parser, classifier, attribution
│   └── ml/               19 signals, rubric, MLP, trainer
├── frontend/             Next.js 14 + Tailwind dashboard
├── vscode-extension/     Sidebar, status bar, score-selection
├── mcp_server/           Claude desktop extension (5 tools)
├── extension/            Chrome extension for claude.ai
└── scripts/              promptly launcher, dev servers, importers
```

Two details worth knowing:

**Transcript noise is excluded.** 37% of recorded "user turns" were never typed by a person — skill files injected into context, slash-command echoes, IDE events. They're long and well-structured, so they scored *highly* and crowded out real prompts. `ingestion/classify.py` filters them.

**Prompts are attributed by the files they touched**, not the directory Claude Code launched in — otherwise work on one repo counts towards another.

---

## Troubleshooting

```bash
promptly doctor
```

Checks logs, database, `.env`, API key, scoring model, auto-sync hook, and both extensions — and prints the exact command to fix anything broken.

---

## License

MIT
