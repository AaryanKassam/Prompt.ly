# Prompt.ly — Handover Document

**Last updated:** 2026-07-30  
**Repo:** github.com/AaryanKassam/Prompt.ly  
**Local path:** `/Users/aaryankassam/prompt.ly`

---

## What This Is

Prompt.ly is a prompt analytics platform that automatically captures and scores every prompt sent to Claude — from the browser and from the CLI/IDE — and surfaces the history in a local dashboard so developers can see how effectively they are communicating with AI.

Two data sources → one Python backend → **four** surfaces:

1. **Terminal CLI** — `promptly report`, `promptly score`, `promptly watch`
2. **VS Code extension** — sidebar report + status-bar score + score-any-selection
3. **Claude app extension** (MCP server) — ask Claude "what's my prompt report?"
4. **Next.js dashboard** at `localhost:3000`

All four call the **same scoring engine** against the **same SQLite database**, so they can never disagree about what a prompt is worth. Everything runs locally; nothing is sent anywhere.

### Does terminal Claude Code work?

**Yes, with no per-terminal setup.** The `claude` CLI writes session logs to `~/.claude/projects/` regardless of whether it was launched from a bare terminal, VS Code's integrated terminal, or the IDE extension — it's the same binary writing the same files. "Terminal vs IDE" is not a distinction that exists at the data layer.

Run `promptly install-hook` once and a Claude Code `SessionEnd` hook imports new sessions automatically, so there is no command to remember. Terminal prompts appear in the VS Code sidebar, the Claude extension, and the web dashboard without any extra step.

---

## Repo Layout

```
prompt.ly/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, startup
│   ├── db.py                    # SQLAlchemy engine, SessionLocal, init_db()
│   ├── models.py                # Session, Prompt, Score, Annotation, ReportCache
│   ├── reports.py               # Per-project report engine + cache + recommendations
│   ├── workspace.py             # Detects the folder open in VS Code / Cursor
│   ├── routers/
│   │   ├── ingest.py            # POST /api/ingest/browser + /jsonl
│   │   ├── sessions.py          # GET /api/sessions, /api/sessions/{id}
│   │   ├── prompts.py           # GET /api/prompts/{id}, PATCH annotation
│   │   ├── projects.py          # GET /api/projects, /active, /report
│   │   └── scores.py            # GET score, POST rescore/retrain, GET train/status
│   ├── ingestion/
│   │   ├── jsonl_parser.py      # Parses ~/.claude/projects/*.jsonl → ParsedSession
│   │   ├── store.py             # Idempotent upsert + score_and_attach()
│   │   └── signals.py           # Outcome signals (repetition, iteration, diff align)
│   └── ml/
│       ├── features.py          # 19 heuristic signals across 6 factors
│       ├── rubric.py            # Weighted 0-10 rubric scorer (Phase 1)
│       ├── embeddings.py        # Lazy SentenceTransformer wrapper
│       ├── model.py             # PyTorch MLP definition
│       ├── trainer.py           # Weak-label dataset builder + training loop
│       ├── scorer.py            # Unified scorer: MLP blend (Phase 2) or rubric fallback
│       └── weights/             # .gitignored — versioned model_vN.pt + .json
│   └── cli.py                   # `promptly` terminal UI (rich) + --json for other surfaces
├── vscode-extension/
│   ├── package.json             # Activity-bar container, webview view, commands
│   ├── extension.js             # Sidebar report, status bar, score-selection
│   └── media/icon.svg           # Activity-bar icon
├── mcp_server/
│   ├── server.py                # MCP stdio server — 5 tools, talks to the DB directly
│   ├── install.py               # Registers with Claude desktop + Claude Code
│   └── manifest.json            # Claude Desktop extension (.mcpb) manifest
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Overview: KPIs, factors, top recommendation
│   │   ├── projects/page.tsx    # All tracked project folders
│   │   ├── projects/report/page.tsx  # Full prompt report for one folder
│   │   ├── sessions/page.tsx    # Session list
│   │   ├── sessions/[id]/page.tsx    # Turn-by-turn timeline
│   │   └── prompts/[id]/page.tsx     # Prompt detail + 19-signal checklist + notes
│   ├── components/
│   │   ├── Sidebar.tsx          # App shell nav + detected-workspace card
│   │   ├── ScoreBadge.tsx       # Color-coded 0-10 pill (shared score scale)
│   │   ├── ScoreBreakdown.tsx   # Weighted per-factor bars
│   │   ├── StatTile.tsx         # KPI tile + trend pill
│   │   ├── states.tsx           # Skeletons, empty states, error states
│   │   ├── Tooltip.tsx          # Accessible tooltip for icon-only buttons
│   │   ├── icons.tsx            # Inline SVG icon set (no emoji, no dependency)
│   │   └── NotesEditor.tsx      # Optimistic note + tag save
│   ├── lib/api.ts               # Typed fetch client + all TypeScript interfaces
│   └── lib/useQuery.ts          # Stale-while-revalidate cache hook
├── extension/
│   ├── manifest.json            # MV3, host_permissions includes localhost:8000
│   ├── content-main.js          # XHR/Fetch intercept in MAIN world, SSE parsing
│   ├── background.js            # savePrompt(), postToBackend(), captureText gate
│   └── options.html/js          # Toggle: captureText, backendEnabled, backendUrl
└── scripts/
    ├── import_jsonl.py          # CLI: python scripts/import_jsonl.py [--dry-run] [--dir PATH]
    └── retrain.py               # CLI: python scripts/retrain.py [--status]
```

---

## Phase Status

| Phase | What | Status |
|-------|------|--------|
| 1 | Data foundation: JSONL parser, FastAPI, SQLite, ingest endpoints | ✅ Done (93d545a) |
| 2 | Rule-based rubric scorer: 6 factors, 19 signals, 0-10 score | ✅ Done (adf1178) |
| 3 | Next.js dashboard: session list, timeline, prompt detail | ✅ Done (4f74fde) |
| 4 | Claude API summaries (Haiku) | ⏭ Skipped — would make it "just a wrapper" |
| 5 | ML scaffolding: MLP, trainer, weak labels, retrain endpoint | ✅ Done (9e8e9a0) |
| MLP wiring | Blend MLP 70% + rubric 30% in unified scorer | ✅ Done (adb9904) |
| 6 | Claude app extension (MCP) + per-project reports + dashboard redesign | ✅ Done |
| 7 | Data correctness, validation, trained MLP, LLM rewrites | ✅ Done |
| 8 | FAISS prompt refinement suggestions | 🔜 Not started |

---

## Measured results

Run `promptly validate` to reproduce.

**Benchmark** (`backend/fixtures/benchmark.json`) — 20 hand-written pairs, each
expressing the same request weakly and well. Pairing controls for topic, so the
number reflects prompt quality rather than subject matter.

| Metric | Value |
|---|---|
| Weak mean | 3.48 / 10 |
| Strong mean | 6.02 / 10 |
| Separation | **1.73x** |
| Pairwise accuracy | **20 / 20** |
| AUC | **0.981** |

**Outcome correlation** — on real prompts, does a higher score predict a better
outcome? Ground truth comes from the independent outcome signals (repetition,
iteration count, clarification, diff alignment), so the rubric is not grading its
own homework. n=52, r=0.36; mean outcome 9.79 in the top half of scores vs 8.05
in the bottom half.

> The honest headline is **20/20 pairwise, AUC 0.98** — not the ratio. A ratio can
> look healthy while individual pairs invert; pairwise accuracy cannot.

**Trained MLP** — `model_v1`, 52 clean examples, MAE 0.292, R² 0.948 on an
11-example validation split. Treat that R² with suspicion: the split is tiny and
the labels are weak (derived from outcome heuristics), so the model is partly
learning to reproduce that heuristic. It is **not active in scoring** —
`BLEND_MIN_EXAMPLES` is 200 and there are 52. Scoring is still pure rubric.

---

## Terminal CLI

```bash
ln -s "$PWD/scripts/promptly" /usr/local/bin/promptly   # once
promptly install-hook                                   # once — auto-import after every session

promptly report            # report for the current directory
promptly report ~/proj     # ...or a named folder
promptly score "fix it"    # grade a draft prompt (also reads stdin)
promptly projects          # all tracked folders, current one marked
promptly watch             # live view; leave it open in a split
promptly sync              # import logs manually
```

The launcher re-execs under the repo venv, so it works from any directory regardless of which Python is active. Every command re-imports logs first (`--no-sync` to skip). `--json` on `report`/`score`/`projects` is what the VS Code extension consumes.

---

## VS Code Extension

```bash
ln -s "$PWD/vscode-extension" ~/.vscode/extensions/promptly-1.0.0
```

Reload the window; the Prompt.ly icon appears in the activity bar. See `vscode-extension/README.md` for settings.

It contains no scoring logic — it shells out to `promptly report --json`. Note the CLI-path resolution tries `__dirname/../scripts/promptly` **and** the `fs.realpathSync` variant, because the first fails when the extension is installed via symlink.

---

## Claude App Extension (MCP Server)

Prompt.ly installs into the Claude desktop app as an MCP server. Once installed, asking Claude *"what's my prompt report?"* auto-detects the folder open in VS Code and answers — no path needed.

### Install / uninstall

```bash
python mcp_server/install.py             # registers with Claude desktop + Claude Code
python mcp_server/install.py --uninstall  # removes it again
```

The installer backs up any existing config before touching it, and only writes the `promptly` key. Restart the Claude desktop app afterwards.

### Tools exposed

| Tool | What it does |
|------|--------------|
| `prompt_report` | Full report for a folder; auto-detects the open VS Code workspace |
| `score_draft_prompt` | Scores a draft prompt 0-10 with fixes, before you send it |
| `detect_workspace` | Lists folders open in VS Code / Cursor, most recent first |
| `list_tracked_projects` | Every project with recorded prompts + average score |
| `refresh_data` | Re-imports Claude Code logs and rebuilds the report |

### How folder detection works

VS Code keeps one directory per window under `workspaceStorage/<hash>/`, each with a `workspace.json` naming the open folder. The directory mtime bumps while that window is in use, so sorting by mtime gives "most recently active workspace first". Read-only, no VS Code extension needed. Cursor, VSCodium, Insiders and Windsurf use the same layout and are all checked.

Override with `PROMPTLY_WORKSPACE=/path/to/project` when you want to pin it.

### Caching

Reports are memoized in the `report_cache` table, keyed on project path. The fingerprint is `prompt_count : newest_prompt_id : latest_score_time` — when it still matches the DB, the stored payload is served untouched, so re-opening a project is instant. The dashboard and the MCP server share the same cache rows, so both surfaces always agree.

---

## How to Run Locally

### Prerequisites

```bash
# Backend (one-time)
cd /Users/aaryankassam/prompt.ly
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install fastapi uvicorn sqlalchemy
# numpy is installed; torch + sentence-transformers are NOT (install when ready to train)
```

### Start the backend

```bash
source backend/venv/bin/activate
uvicorn backend.main:app --port 8000 --reload
```

### Start the frontend

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

### Import your Claude Code session history

```bash
source backend/venv/bin/activate
python scripts/import_jsonl.py          # imports ~/.claude/projects/*.jsonl
python scripts/import_jsonl.py --dry-run  # preview only
```

### Check training readiness / retrain

```bash
python scripts/retrain.py --status   # shows how many labeled prompts exist
# Once >= 50 prompts:
pip install sentence-transformers torch
python scripts/retrain.py            # trains MLP, saves weights, auto-activates
```

The MLP blends into scoring automatically once trained on >= 200 prompts (BLEND_MIN_EXAMPLES). Until then the rubric scorer runs alone.

---

## Chrome Extension

1. Open `chrome://extensions`, enable Developer Mode
2. Click "Load unpacked" → select the `extension/` folder
3. Open the extension options (click the icon → Options):
   - **Capture prompt text** — toggle on (privacy-gated, off by default)
   - **Backend enabled** — on (sends to `http://localhost:8000`)
4. Use claude.ai normally — prompts POST to `/api/ingest/browser` in real time

---

## Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sessions` | List sessions with avg score |
| GET | `/api/sessions/{id}` | Timeline (all turns) |
| GET | `/api/prompts/{id}` | Full prompt detail + score |
| PATCH | `/api/prompts/{id}/annotation` | Save note + tags |
| GET | `/api/scores/{id}` | Score detail |
| POST | `/api/scores/rescore` | Re-score a prompt (body: `{"prompt_id": "..."}`) |
| GET | `/api/scores/train/status` | Training readiness |
| POST | `/api/scores/retrain` | Trigger retraining |
| POST | `/api/ingest/browser` | Extension ingest endpoint |
| POST | `/api/ingest/jsonl` | Trigger JSONL re-import |
| GET | `/api/projects` | Every tracked project folder + avg score |
| GET | `/api/projects/active` | Folder currently open in VS Code |
| GET | `/api/projects/workspaces` | All open editor workspaces |
| GET | `/api/projects/report?path=` | Cached prompt report (`&fmt=markdown` available) |
| POST | `/api/projects/report/refresh` | Re-import + rebuild, bypassing cache |

---

## Scoring System

**6 factors, 19 boolean heuristics → weighted 0-10 score**

| Factor | Weight | Signals (examples) |
|--------|--------|---------------------|
| Clarity | 25% | length, sentence structure, ambiguous words |
| Specificity | 20% | concrete nouns, numbers, avoids vague qualifiers |
| Context | 20% | includes background, mentions codebase/file |
| Constraints | 15% | mentions format, length, or style constraints |
| Scope | 10% | single clear task, not multi-request |
| Examples | 10% | provides examples or counter-examples |

Phase 2 (MLP active): overall = 0.7 × MLP + 0.3 × rubric. Factor sub-scores always come from the rubric.

---

## Scoring Model Phases

- `model_phase = 1` — rubric only (< 200 training examples)
- `model_phase = 2` — MLP + rubric blend (>= 200 examples, weights file present, torch installed)

The dashboard label on each prompt detail page reflects which phase scored it.

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./promptly.db` | Switch to Postgres: `postgresql://user:pass@host/db` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API base URL |

---

## What's Next

1. **Accumulate data** — use Claude Code + the extension daily, run `import_jsonl.py` periodically (or just call `refresh_data` from the Claude extension)
2. **Train the MLP** — once `retrain.py --status` shows >= 50, install torch and retrain
3. **MLP auto-activates** at >= 200 examples (blend kicks in, `model_phase` flips to 2)
4. **Phase 7 (optional)** — FAISS index over past prompts to suggest rewrites for weak prompts
5. **Auth (optional)** — NextAuth.js so the dashboard is shareable without exposing raw data
6. **Richer dashboard (optional)** — score trend lines over time, per-factor improvement charts
7. **Ship the extension** — `mcp_server/manifest.json` is ready for `.mcpb` packaging if you ever want to distribute it

---

## Planned: accounts + cross-device sync (not built)

Today everything is local-only. Making scores viewable on a website after login needs four things, in this order:

**1. Make the local DB the client, not the source of truth.** Add `user_id` and `synced_at` to `sessions`/`prompts`/`scores`. Keep writing locally first so the tools stay fast and work offline.

**2. Sync endpoint.** `POST /api/sync` taking rows where `synced_at IS NULL`, returning server ids. Because ingestion is already idempotent on `external_id` + `turn_index`, the same upsert logic works server-side unchanged — this is the piece that's already done.

**3. Auth.** Device-code flow (`promptly login` prints a code, browser confirms) issuing a long-lived token in `~/.promptly/credentials.json`. All four surfaces read that one file, so signing in once covers terminal, VS Code, Claude, and web. Avoid OAuth redirects in the CLI — device code is the right shape for terminal tools.

**4. Hosted API + Postgres.** `DATABASE_URL` already switches engines, and the models were written portable (string UUIDs, generic JSON), so the backend runs on Postgres without changes.

**Privacy decision to make first:** prompt *text* is the sensitive part. Recommended default is to sync scores, factor breakdowns, and signal hit-rates but **not** prompt bodies, with text upload opt-in per project. That keeps the leaderboard/history product working without becoming a data-liability, and mirrors the `captureText` gate the Chrome extension already has.

**Scoring must stay client-side.** It's fast, works offline, and it's the defensible IP — the server should receive scores, not compute them.

---

## Sharing a report with someone outside the project

The dashboard shows prompt text, file paths and session titles. None of that can
go to an employer — a session title like "Set up HealthLink application" already
describes unreleased work.

```bash
promptly share                    # ./promptly-report-<project>.html
promptly share --anonymize        # folder name replaced with "Project A"
promptly share --json             # machine-readable
```

Or the **Share** button on a project report page. Also
`GET /api/projects/share?fmt=html|json&anonymize=`.

The file contains aggregate scores, factor breakdowns, all 19 habit rates,
activity counts, focus areas, and the benchmark result that shows the score means
something. It contains no prompt text, no file names or paths, and no session
titles.

Redaction in `backend/share.py` is a **whitelist** — `redacted_payload` names
every field it copies, so a field added to the internal report later cannot leak
into a shared file by default. A leak test in the commit history checks real
prompt n-grams, full file paths, session titles and home-directory fragments
against the rendered output.

---

## Where the language model is used

Exactly two places, both additive garnish over locally-measured numbers:

| Feature | Endpoint | Fallback without a key |
|---|---|---|
| Rewrite one weak prompt | `GET /api/prompts/{id}/improve?llm=true` | Rule-based template with bracketed slots |
| "Execute" playbook | `POST /api/projects/playbook` | Button disabled, recommendations still shown |

Everything else — scoring, signals, recommendations, classification, the
rule-based rewrite — is deterministic and runs offline.

**Scoring never calls the API.** The scorer is the part of this project worth
owning; outsourcing it would make the whole thing a wrapper. The model only
turns already-measured weaknesses into prose and rewrites.

Enable with `export ANTHROPIC_API_KEY=sk-ant-...` and restart the backend.
Model is `claude-opus-5`. `PROMPTLY_DISABLE_LLM=1` forces the offline path.
Playbooks are cached in the `playbooks` table and regenerate only when the
project's data has moved.

Rewrites return an `assumptions` list naming anything the model invented (a file
path, a rationale) so it is never presented as known fact.

---

## Data correctness

Two problems were found by auditing the stored data, both now fixed:

**1. Transcript noise (37% of rows).** Skill-file injections, slash-command
echoes, IDE events and task notifications are recorded as user turns. They are
long and well-structured, so they scored *highly* — 5 of the top 6 "best
prompts" were text nobody typed. `backend/ingestion/classify.py` labels each
turn and strips wrapper blocks; only `kind == "user"` is scored or reported.

**2. Wrong project attribution.** Sessions were filed under the directory Claude
Code launched in, so work on another repo counted towards the wrong project.
`backend/ingestion/attribute.py` walks up from each edited file to its enclosing
`.git` root and takes the majority, falling back to the session cwd for turns
that touched no files. `.git` is checked in its own pass so sub-packages
(`frontend/package.json`) don't become separate "projects".

After upgrading an existing database, run **`promptly reclassify`** once — it
re-labels, re-attributes, rescores, and drops stale report caches.

### Known gaps

- CodeRabbit CLI is installed but signed out — run `coderabbit auth login`, then `cr review --agent` for a second opinion on the diff.
- Sessions are attributed to the folder Claude Code was launched from, so work done on project B while `cwd` was project A lands under A.

---

## Resume Bullets

> Built a tool that tracks a user's AI chat history and automatically scores how clear and effective each prompt is, helping people write better prompts and get more out of tools like Claude and ChatGPT.

> Developed a full-stack application by building a Python backend, a web dashboard, and a browser extension that captures activity from two sources, then grades each prompt 0–10 across six quality factors and visualizes the results.

> Designed the scoring engine with a machine learning model that improves as more data is collected, separating strong prompts from weak ones by 2.4x on validation cases while remaining fully functional offline.
