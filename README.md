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

Requires Python 3.10+ and Claude Code. One line:

```bash
git clone https://github.com/AaryanKassam/Prompt.ly.git && cd Prompt.ly && ./setup
```

`./setup` creates the virtualenv, installs the five dependencies, puts `promptly` on your PATH, imports your existing Claude Code history, registers the auto-import hook, and installs the VS Code extension into every VS Code-family editor it finds, naming each one as it goes.

It is **safe to re-run**: every step checks before it acts, so it doubles as a repair command when something drifts.

```bash
./setup --no-path      # don't touch your shell rc file
./setup --no-hook      # skip the auto-import hook
./setup --no-vscode    # skip the editor extension
```

The only thing it changes outside the repo is one `export PATH` line in your `.zshrc`/`.bashrc`, and only if `~/.local/bin` isn't already on your PATH. It says so when it does.

### The three commands you'll actually use

```bash
promptly score "your draft prompt"   # rate + token cost BEFORE you send it
promptly report                      # how you're prompting in this folder
./scripts/dev                        # launch the dashboard at localhost:3000
```

Everything else is optional. `promptly doctor` re-checks every part of the setup.

Three optional extras, each needed for exactly one feature:

```bash
backend/venv/bin/pip install anthropic                     # prompt rewrites + playbook
backend/venv/bin/pip install "mcp[cli]"                    # Claude desktop extension
backend/venv/bin/pip install torch sentence-transformers   # training the MLP
```

<details>
<summary><b>Setting it up by hand instead</b></summary>

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
ln -s "$PWD/scripts/promptly" ~/.local/bin/promptly    # put it on your PATH
promptly install-hook                                  # auto-import after each session
promptly sync                                          # import existing history
```

</details>

### Terminal

`install-hook` registers a Claude Code `SessionEnd` hook, so new sessions import themselves and there's nothing to remember to run. Run `promptly` on its own to see every command.

> **Using the VS Code integrated terminal?** Nothing extra to install. It is an ordinary interactive shell, so it reads the same `~/.zshrc` (or `~/.bashrc`) that `./setup` configured. Run the same `promptly` commands there as in Terminal.app, one install covers both. If `promptly` works in Terminal but not in VS Code, the integrated terminal is likely set to a non-interactive or different shell; the fix is to add `export PATH="$HOME/.local/bin:$PATH"` to the rc file that shell reads.

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

`./scripts/dev` frees the ports before binding them, so it doubles as a restart.

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

Already installed by `./setup`, just reload the window (`Cmd+Shift+P` → *Developer: Reload Window*) and the Prompt.ly icon appears in the activity bar. To link it by hand:

```bash
ln -s "$PWD/vscode-extension" ~/.vscode/extensions/promptly-1.0.0
```

- **Sidebar**: score, trend, factor bars, token cost, recommendations, worst prompts for the folder you have open
- **Status bar**: this project's score, always visible
- **Right-click any selection** → *Prompt.ly: Score selected text as a prompt*
- Multi-root aware: re-targets when you switch between projects

It holds no scoring logic; it shells out to `promptly report --json`. If the CLI isn't found automatically, set `promptly.cliPath` in settings to the absolute path of `scripts/promptly`.

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

It also correlates scores against independent outcome signals (repetition, iteration count, clarification requests, diff alignment) on real prompts, so the rubric isn't grading its own homework. Across every project tracked on this machine, `promptly validate` reports **r = 0.142** on 284 scored prompts.

That figure fell from the **0.298** reported here previously, and it is worth being precise about why, because only part of it is the rubric's doing:

| Rubric | Corpus | r |
|---|---|---|
| Previous | 156 prompts | 0.298 |
| Previous | 284 prompts (today) | 0.178 |
| Current | 284 prompts (today) | 0.142 |

Most of the drop is the corpus nearly doubling, which is what the caveat at the end of this section always warned would happen. The rubric change accounts for the remaining **0.036**: making the scorer fairer to long structured prompts cost a little outcome correlation on this corpus, while the paired benchmark went *up* (AUC 0.981 to 0.985). That is a trade made knowingly, and stated rather than buried.

Either way the number is modest, which is worth stating plainly rather than burying: the benchmark separates hand-written good and bad prompts almost perfectly, but predicting real-world outcomes from prompt text alone is a much harder problem, and this metric still has a long way to go.

Against token cost specifically, the efficiency factor correlates **r = −0.250** with output tokens: higher efficiency, fewer tokens burned, in the direction it was designed to predict.

> Every figure in this section that comes from *real prompts*, the correlations and the token totals above, is a snapshot of one machine's corpus on 2026-09-12 and moves as that corpus grows. The benchmark table does not. Run `promptly validate` and `promptly report` for your own numbers.

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
./setup            # re-run to repair a broken install; every step is idempotent
```

`doctor` checks logs, database, `.env`, API key, scoring model, auto-sync hook and both extensions. `./setup` rebuilds whatever is missing without touching what already works.

---

## License

MIT
