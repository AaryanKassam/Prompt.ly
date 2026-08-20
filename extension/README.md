# Prompt.ly browser extension

Captures your prompts on claude.ai so browser conversations land in the same
dashboard as your Claude Code sessions.

## Why it exists

The JSONL parser reads `~/.claude/projects/`, which covers Claude Code in every
form — terminal, integrated terminal, IDE extension. It cannot see claude.ai,
because that conversation never touches your filesystem. This extension is the
only way browser prompts reach Prompt.ly.

## Install

1. Open `chrome://extensions` and turn on **Developer mode**
2. **Load unpacked** → select this `extension/` folder
3. Click the Prompt.ly icon → **Options**:
   - **Capture prompt text** — off by default. Leave it off and only counts and
     token totals are stored; turn it on to get scores, since the scorer needs
     the words.
   - **Send to backend** — on. Posts to `http://localhost:8000`.
4. Use claude.ai normally.

The backend must be running for capture to reach the database:

```bash
uvicorn backend.main:app --port 8000
```

Prompts are posted to `POST /api/ingest/browser`, classified, and scored on
arrival — the same pipeline Claude Code sessions go through, so a browser prompt
and a terminal prompt are scored identically.

## Privacy

Everything stays on your machine. The extension talks to `localhost` only —
`host_permissions` lists exactly two origins, `claude.ai` (to read the page) and
`localhost:8000` (to store what it read). Nothing is sent anywhere else.

Text capture is off until you turn it on, and can be turned back off at any
time without losing previously stored prompts.

## Where browser prompts appear

Browser sessions have no project folder, so they show under **Sessions** in the
dashboard rather than inside a per-project report — a claude.ai conversation
isn't tied to a repository the way a Claude Code session is.

## Files

| File | Role |
|---|---|
| `content-main.js` | Runs in the page's MAIN world; intercepts XHR/fetch and parses the SSE stream |
| `content-isolated.js` | Bridges page events back to the extension |
| `background.js` | Service worker: builds the record, applies the capture-text gate, POSTs to the backend |
| `options.html/js` | Capture and backend settings |
| `popup.html/js` | Toolbar summary |
| `report.html/js` | Standalone local report, for use without the dashboard |
