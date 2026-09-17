# prompt.ly

Scores how effectively you prompt Claude, per project, then shows you how to improve.

Prompt.ly reads the Claude Code session logs already on your machine, grades every prompt 0–10 across eight factors (six for quality, one for token efficiency, one for whether a cheaper model would have worked), and reports how you're doing in whichever project you're working on. It runs entirely locally.

![Prompt.ly dashboard](docs/dashboard.png)

---

## Why

Everyone using an AI coding assistant is writing dozens of prompts a day, and nobody gets feedback on any of them.

Prompt.ly makes it visible, in both directions. It found that 97% of my prompts never paste the actual error and 92% never name a file, and that a single two-word prompt (`"do both"`) cost 57,303 output tokens.

---

## Four ways to use it

All four read the same database and call the same scoring engine, so they can never disagree about what a prompt is worth.

| Surface | Best for |
|---|---|
| **Terminal** | Scoring a draft *before* you send it, with its projected token cost; cwd-aware reports |
| **VS Code** | A sidebar score for the project you're in, while you work |
| **Claude app** | Asking "how's my prompting?" in conversation |
| **Dashboard** | Deep dives, expandable factors, the playbook, sharing |

---

## Install

Requires Python 3.10+, Node.js 18+ (for the dashboard), and Claude Code. Setup is native on every OS: macOS and Linux get a bash script, Windows gets a PowerShell script that does the same eight things; nothing here needs WSL or Git Bash.

**macOS / Linux:**

```bash
git clone https://github.com/AaryanKassam/Prompt.ly.git && cd Prompt.ly && ./setup
```

**Windows** (PowerShell: press <kbd>Win</kbd>, type "PowerShell", open it):

```powershell
git clone https://github.com/AaryanKassam/Prompt.ly.git
cd Prompt.ly
.\setup.ps1
```

> First time running a local script? Windows blocks unsigned `.ps1` files by default. If you get an "execution policy" error, run this once in the same window, then retry: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. It only relaxes the policy for the current PowerShell process, not system-wide.

Either script creates the virtualenv, installs the five Python dependencies, installs the dashboard's npm dependencies, puts `promptly` on your PATH, imports your existing Claude Code history, registers the auto-import hook, and installs the VS Code extension into every VS Code-family editor it finds, naming each one as it goes.

Both are **safe to re-run**: every step checks before it acts, so re-running doubles as a repair command when something drifts.

```bash
./setup --no-path      # don't touch your shell rc file
./setup --no-hook      # skip the auto-import hook
./setup --no-vscode    # skip the editor extension
```

```powershell
.\setup.ps1 -NoPath      # don't touch your user PATH
.\setup.ps1 -NoHook      # skip the auto-import hook
.\setup.ps1 -NoVSCode    # skip the editor extension
```

The only thing either script changes outside the repo is how `promptly` gets found: macOS/Linux add one `export PATH` line to `.zshrc`/`.bashrc`; Windows sets the `PATH` User environment variable via `[Environment]::SetEnvironmentVariable`, both only if `~/.local/bin` isn't already on the PATH. Each says so when it does, and on Windows the VS Code extension is copied in rather than symlinked (Windows symlinks need Developer Mode or admin rights); re-run the setup script after updating the extension to refresh it.

### The three commands you'll actually use

Identical on every OS once `promptly` is on your PATH:

```bash
promptly score "your draft prompt"   # rate + token cost BEFORE you send it
promptly report                      # how you're prompting in this folder
promptly dashboard                   # launch the dashboard at localhost:3000
```

Everything else is optional. `promptly doctor` re-checks every part of the setup.

Three optional extras, each needed for exactly one feature:

```bash
backend/venv/bin/pip install anthropic                     # prompt rewrites + playbook
backend/venv/bin/pip install "mcp[cli]"                    # Claude desktop extension
backend/venv/bin/pip install torch sentence-transformers   # training the MLP
```

On Windows, the venv's `pip` is at `backend\venv\Scripts\pip.exe` instead of `backend/venv/bin/pip`.

<details>
<summary><b>Setting it up by hand instead</b></summary>

**macOS / Linux:**

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
ln -s "$PWD/scripts/promptly" ~/.local/bin/promptly    # put it on your PATH
promptly install-hook                                  # auto-import after each session
promptly sync                                          # import existing history
```

**Windows (PowerShell):**

```powershell
python -m venv backend\venv
backend\venv\Scripts\pip.exe install -r backend\requirements.txt
# Symlinks need admin rights on Windows, so copy the launcher onto your PATH
# instead. Any folder already on PATH works; $HOME\.local\bin matches what
# setup.ps1 uses.
New-Item -ItemType Directory -Force -Path "$HOME\.local\bin" | Out-Null
Copy-Item .\scripts\promptly.cmd "$HOME\.local\bin\promptly.cmd"
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$HOME\.local\bin", "User")
# open a new terminal, then:
promptly install-hook                                  # auto-import after each session
promptly sync                                          # import existing history
```

</details>

### Terminal

`install-hook` registers a Claude Code `SessionEnd` hook, so new sessions import themselves and there's nothing to remember to run. Run `promptly` on its own (or `promptly help`) to see every command.

> **Using the VS Code integrated terminal?** Nothing extra to install, on any OS. It's an ordinary interactive shell, so it reads the same PATH configuration setup just changed: the same `.zshrc`/`.bashrc` on macOS/Linux, the same user `PATH` variable on Windows. Run the same `promptly` commands there as in Terminal.app or PowerShell; one install covers both. If `promptly` works in one but not the other, the integrated terminal is likely a non-interactive shell or wasn't reopened after setup ran; open a new terminal, or on macOS/Linux add `export PATH="$HOME/.local/bin:$PATH"` to the rc file that shell reads.

**Score a prompt before you send it**, the thing only the terminal can do:

```bash
promptly score "fix the parser"    # inline
promptly score -c                  # score whatever you just copied
promptly score -e                  # compose in $EDITOR
cat draft.txt | promptly score     # from a file
```

It prints the score, the factor breakdown, and a projected token cost:

```
╭──────────────────────── projected token cost ────────────────────────╮
│ 17 tokens to send  →  ~1,980 tokens back   (you capped the reply)    │
╰──────────────────────────────────────────────────────────────────────╯
```

The projection comes from the median output observed for prompts with the same efficiency signals. It is a guide, not a guarantee: a short prompt that kicks off a large refactor will sail straight past it.

Then the rest:

| Command | Short | What |
|---|---|---|
| **`promptly help`** | | **Every command, grouped by when you'd reach for it** |
| `promptly dashboard` | `ui` | Open the full dashboard in a browser (starts the servers if needed) |
| `promptly report [path]` | `r` | Report for a folder, defaulting to the current one |
| `promptly projects` | `p` | Every tracked folder |
| `promptly watch` | `w` | Live report, refreshes as you work |
| `promptly hide` | | Drop a turn from your score (see below) |
| `promptly hidden` | | List the turns you've excluded |
| `promptly unhide <id>` | | Put one back |
| `promptly share` | | Redacted report safe to send to someone else |
| `promptly doctor` | `check` | Check the setup and print the fix for anything broken |
| `promptly sync` | | Import new sessions now |
| `promptly validate` | | Measure the scorer against the benchmark |
| `promptly workspaces` | | Folders currently open in VS Code / Cursor |
| `promptly reclassify` | | Re-label and rescore after an upgrade |

**`promptly help` is the one to remember.** It prints every command grouped by when you'd reach for it, with the short forms. Running `promptly` with no arguments prints the same thing, so there is nothing to memorise. `--json` works on most commands for scripting.

### Opening the dashboard

```bash
promptly dashboard          # starts both servers if they aren't up, then opens the browser
promptly dashboard --no-open   # start the servers, don't open a browser
```

The dashboard is the deep-dive surface: expandable factors, per-signal evidence, the playbook, and sharing. It runs on `localhost:3000` with the API on `localhost:8000`. To drive the servers directly instead:

```bash
./scripts/dev            # start both
./scripts/dev backend    # API only
./scripts/dev frontend   # dashboard only
./scripts/dev stop       # stop both
```

```powershell
.\scripts\dev.ps1            # start both
.\scripts\dev.ps1 backend    # API only
.\scripts\dev.ps1 frontend   # dashboard only
.\scripts\dev.ps1 stop       # stop both
```

Either frees the ports before binding them, so running it again doubles as a restart. `promptly dashboard` (above) calls whichever one matches your OS automatically. Reach for these directly only when you want the servers without the browser opening.

### Hiding a turn

Not every prompt is work you want graded. Asking a clarifying question mid-task, pulling up a description, checking what a flag does: these are legitimate uses of the tool that score badly *as instructions*, because they aren't instructions. Left in, they drag the project average down and turn the score into something to game rather than something to read.

```bash
promptly hide                # list recent turns and how to pick one
promptly hide --last         # exclude the most recent turn
promptly hide 790f470d       # exclude one by id prefix
promptly hidden              # everything currently excluded, with ids
promptly unhide 790f470d     # put it back
```

Hiding **deletes the score row** rather than flagging it, so no average can pick up a stale number by accident. Unhiding rescores from the prompt text, which means a restored turn is graded by the current rubric rather than whichever one was live when it was first imported.

The launcher re-execs under the repo venv, so it works from any directory regardless of which Python is active.

### VS Code

Already installed by setup, just reload the window (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux → *Developer: Reload Window*) and the Prompt.ly icon appears in the activity bar. To link it by hand:

```bash
ln -s "$PWD/vscode-extension" ~/.vscode/extensions/promptly-1.0.0
```

On Windows, symlinks need admin rights or Developer Mode, so copy instead of linking (re-run after updating the extension to pick up changes):

```powershell
Copy-Item .\vscode-extension "$HOME\.vscode\extensions\promptly-1.0.0" -Recurse -Force
```

- **Sidebar**: score, trend, factor bars, token cost, recommendations, worst prompts for the folder you have open
- **Status bar**: this project's score, always visible
- **Right-click any selection** → *Prompt.ly: Score selected text as a prompt*
- Multi-root aware: re-targets when you switch between projects

It holds no scoring logic; it shells out to `promptly report --json`. If the CLI isn't found automatically, set `promptly.cliPath` in settings to the absolute path of `scripts/promptly`.

### Dashboard

```bash
promptly dashboard       # starts both servers and opens the browser, on any OS
```

Open **http://localhost:3000**. `promptly dashboard --no-open` starts the servers without opening a browser; `./scripts/dev stop` (or `.\scripts\dev.ps1 stop` on Windows) shuts them down.

### Claude app extension

```bash
backend/venv/bin/python mcp_server/install.py       # macOS / Linux
backend\venv\Scripts\python.exe mcp_server\install.py   # Windows
```

Restart the Claude desktop app, then ask *"what's my prompt report?"*. It auto-detects the folder open in your editor. Five tools: `prompt_report`, `score_draft_prompt`, `detect_workspace`, `list_tracked_projects`, `refresh_data`.

### Chrome extension (optional)

Only needed to capture claude.ai; Claude Code is covered by the log parser. See [`extension/README.md`](extension/README.md).

---

## How scoring works

Every prompt is graded 0–10 across eight weighted factors, built from 26 structural signals:

| Factor | Weight | Measures |
|---|---|---|
| Clarity | 21% | One unambiguous action, active voice, no hedging |
| Specificity | 17% | Names files, identifiers, expected output shape |
| Context | 16% | Background, intent, relevant stack |
| **Efficiency** | **15%** | **Tokens spent, and whether the reply size is bounded** |
| Constraints | 12% | What not to change, where to stop |
| Scope | 9% | One task per request, sized to be reviewable |
| **Model fit** | **7%** | **Whether a cheaper model would have done the job** |
| Examples | 3% | Points at real code, an error, or a concrete case |

Factor scores are not linear in the signals met. A factor that meets nothing scores 1.0 rather than 0, and partial credit accrues on a mild curve (`fraction ** 0.90`), because a scale whose top third is unreachable measures nothing at the top. Both constants are calibrated on this machine's corpus, not guessed: at a floor of 2.0 the *lowest* score on 284 real prompts was 5.3, which trades an unusable top of the scale for an unusable bottom.

**Long is not the same as bad.** Three separate signals used to penalise length, so one long prompt was marked down three times for a single attribute, and a detailed handoff document scored worse than a one-line "fix it". Prompts with headings, bullets, numbered steps or fenced code are now exempt from the two *rambling* signals (`clarity.sentence_count_focused`, `scope.task_size_appropriate`) while still paying the honest cost signal in `efficiency.concise_prompt`, because a long prompt does cost more to answer however tidy it is. On the corpus this moved a representative handoff document from 5.6 to 7.2 without moving `"do both"` off the floor.

### Model fit

The only factor that measures money rather than wording. Opus-class models bill $5/$25 per million input/output tokens against Sonnet's $2/$10, so answering a lookup on the heavy model is a 2.5x overspend that no amount of prompt polish recovers. The reverse is also a real cost: a genuinely hard task on a small model buys retries, and three attempts that miss cost more than one answer that lands.

Both signals pass when the model is unknown, so scoring a draft you haven't sent is never penalised for a choice you haven't made. Task weight is a keyword and structure heuristic, not a measured outcome, which is why the factor is weighted below the validated quality factors.

**The scorer is deterministic and runs offline.** No language model is involved in producing a score, that's the point. A rubric you own is defensible; a wrapper around someone else's judgement isn't.

### Token efficiency

Prompt quality and prompt *cost* are different axes, and the second one is where the money goes. `"do both"` scores 4.1/10 and is two words long, and it drew **57,303 output tokens**. Being terse is not the same as being efficient.

So Prompt.ly measures both:

**The `efficiency` factor** predicts cost from the text alone, which is what makes it usable *before* you send:

| Signal | Evidence |
|---|---|
| `concise_prompt` (≤60 words) | **p = 0.0003**, median 5.9k vs 24.3k output tokens |
| `no_filler_phrases` | p = 0.31, not separated |
| `no_redundant_restatement` | p = 0.84, not separated |
| `bounds_response_size` | p = 0.94, not separated |

Measured by Mann–Whitney U on 75 real turns carrying token counts. **Only length separates**, and it separates hard: long prompts drew four times the output.

An earlier run of this table on 45 turns put `no_filler_phrases` at p = 0.094. It did not survive the sample more than doubling, worth recording rather than quietly re-tuning, because it is exactly the kind of result that looks real until it isn't. The three non-separating signals are kept because each still directly causes tokens to be spent, and because a signal that fails to predict *reply length* may still be worth writing; they are not evidence for anything yet. The 15% weight reflects one demonstrated signal out of four, not four. Retune with `PROMPTLY_EFFICIENCY_WEIGHT=0.25`; the other six factors rescale to keep the weights summing to 1.

**Measured token economics** is the other half: what your prompting actually cost, from the transcript.

```
token cost
      total tokens  178,773,152
  context / output  178,223,146 · 550,006
 median per prompt  6,193 out  (typical)
  per file changed  9,483 out
```

Two things worth knowing about these numbers:

- **Context includes cache.** Claude Code caches aggressively, so the raw `input_tokens` field has a median of *2*. Reading it alone understates a project's context cost by four orders of magnitude, this repo's real figure is ~179M, not the 20k a naive reading gives. Prompt.ly sums `input + cache_read + cache_creation`.
- **Cost per file changed is the honest metric.** Raw totals punish a big task for being big. Normalising by work delivered is what makes a one-line fix and a refactor comparable.

Neither number is causal. A prompt that costs 60k tokens may have been doing 60k tokens of legitimate work; these are observational figures on one corpus, and they are labelled that way in the code.

### Does it actually work?

`promptly validate` measures it against a benchmark of 20 hand-written pairs, each expressing the same request once weakly and once well. Pairing controls for topic, so the result reflects prompt quality rather than subject matter.

| Metric | Result |
|---|---|
| Weak mean | 5.40 / 10 |
| Strong mean | 7.45 / 10 |
| **Pairwise accuracy** | **20 / 20** |
| **AUC** | **0.985** |

Those four figures come from a fixed fixture, so they are reproducible: `promptly validate` gives the same answer on your machine as on mine.

It also correlates scores against independent outcome signals (repetition, iteration count, clarification requests, diff alignment) on real prompts, so the rubric isn't grading its own homework. Across every project tracked on this machine, `promptly validate` reports this on 307 scored prompts:

| Statistic | Value | 95% CI |
|---|---|---|
| **Spearman rho** | **0.343** | 0.24 to 0.44 |
| Pearson r | 0.151 | 0.04 to 0.26 |

**The rank correlation is the one to read, and this README previously reported the wrong one.** The outcome label is capped at 10, and 41% of prompts sit exactly on that cap, because "no repetition, no retries, no clarifying question" is the ordinary case rather than the exceptional one. Pearson measures *linear* association and is dragged down hard by that pile-up; Spearman only asks whether better-scored prompts tend to land better, which is the whole claim. On this corpus the difference is a factor of 2.3, and it is a property of the label's shape, not of the rubric.

That also revises a story told here previously. An earlier README reported **r = 0.298** on 156 prompts and then **0.142** on 284, and attributed **0.036** of the fall to a rubric change. The attribution arithmetic was right, but the confidence intervals on those figures are roughly ±0.11 and overlap almost entirely, so the fall was mostly sampling noise being read as a trend. `promptly validate` now prints an interval next to both coefficients so that mistake is harder to repeat.

The number is still modest, which is worth stating plainly rather than burying: the benchmark separates hand-written good and bad prompts almost perfectly, but predicting real-world outcomes from prompt text alone is a much harder problem, and this metric still has a long way to go. The binding constraint is the *label*, not the rubric. Three of its four signals barely fire across 307 prompts (iteration count 10, clarification 11, diff alignment 22, the last because only 40 prompts have any changed files attributed to them at all), so almost all of the label's movement comes from the repetition term. Widening it is the work that would make this figure mean more.

Against token cost specifically, the efficiency factor correlates **r = −0.250** with output tokens: higher efficiency, fewer tokens burned, in the direction it was designed to predict.

> Every figure in this section that comes from *real prompts*, the correlations and the token totals above, is a snapshot of one machine's corpus on 2026-09-17 and moves as that corpus grows. The benchmark table does not. Run `promptly validate` and `promptly report` for your own numbers.

---

## Where a language model *is* used

Two optional features, both garnish over numbers measured locally first:

- **Rewrite this prompt**: a full rewrite of one weak prompt
- **Playbook**: turns your measured weaknesses into a personalised guide with your own prompts rewritten

Both need an API key. Everything else works without one.

```bash
cp .env.example .env      # then paste your key into ANTHROPIC_API_KEY
./scripts/dev             # restart to pick it up
```

Rewrites return an **assumptions list** naming anything the model invented, a file path, a rationale, so it's never presented as fact you can rely on.

---

## Sharing a report

The dashboard shows your prompt text, file paths and session titles. None of that can go to an employer.

```bash
promptly share              # ./promptly-report-<project>.html
promptly share --anonymize  # ...with the folder name hidden
```

<img src="docs/shareable-report.png" alt="Shareable report" width="480">

The file carries aggregate scores, factor breakdowns, all 23 habit rates, aggregate token cost, activity counts and the benchmark result. It contains **no prompt text, no file paths, no session titles**. Redaction is a whitelist, so a field added to the internal report later cannot leak into a shared file by default.

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
├── setup                 One-command installer (safe to re-run)
├── backend/              FastAPI + SQLAlchemy
│   ├── cli.py            The `promptly` terminal UI
│   ├── reports.py        Per-project report engine, cache, token economics
│   ├── improve.py        Offline rewrite of a weak prompt
│   ├── share.py          Redacted shareable report
│   ├── validation.py     Benchmark + outcome correlation
│   ├── workspace.py      Detects the folder open in VS Code / Cursor
│   ├── llm.py            The only language-model calls in the project
│   ├── ingestion/        JSONL parser, classifier, attribution
│   └── ml/               26 signals, rubric, MLP, trainer
├── frontend/             Next.js 14 + Tailwind dashboard
├── vscode-extension/     Sidebar, status bar, score-selection
├── mcp_server/           Claude desktop extension (5 tools)
├── extension/            Chrome extension for claude.ai
└── scripts/              promptly launcher, dev servers, importers
```

Two details worth knowing:

**Transcript noise is excluded.** A large share of recorded "user turns" were never typed by a person: between a third and a half of this repo's, depending on how much real work has happened since. Of 169 rows: 35 system notices, 14 skill injections, 10 slash-command echoes and 1 empty turn, against 109 real prompts. They're long and well-structured, so they scored *highly* and crowded out genuine prompts in the rankings. `ingestion/classify.py` filters them.

**Prompts are attributed by the files they touched**, not the directory Claude Code launched in, otherwise work on one repo counts towards another.

---

## Troubleshooting

```bash
promptly doctor    # what's wired up, and the exact fix for anything that isn't
./setup            # macOS/Linux: re-run to repair a broken install
.\setup.ps1         # Windows: same thing
```

`doctor` checks logs, database, `.env`, API key, scoring model, auto-sync hook, both extensions, and the dashboard's npm dependencies, the same way on every OS. Either setup script rebuilds whatever is missing without touching what already works; both are idempotent.

**Windows-specific issues:**

| Symptom | Fix |
|---|---|
| `.ps1 cannot be loaded because running scripts is disabled` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once in that PowerShell window, then retry. |
| `promptly` not found after setup | Open a new terminal: `setup.ps1` sets the `PATH` for new processes, not the one it ran in. |
| `promptly score -c` returns nothing | Needs PowerShell on PATH (bundled with every supported Windows version) to read the clipboard; `cmd.exe`-only environments without PowerShell aren't supported. |

---

## License

MIT
