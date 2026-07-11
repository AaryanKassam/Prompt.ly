# prompt.ly

A lightweight browser extension that silently tracks your Claude.ai prompt usage and token estimates, surfacing a clean usage report without storing any prompt text.

---

## What it tracks

- Number of prompts sent
- Estimated input tokens (your message)
- Estimated output tokens (Claude's response)
- Per-conversation breakdown
- Daily usage over a configurable rolling window (7 / 30 / 90 days)

Token counts are estimates based on the ~4 characters per token approximation used by Claude models. No prompt text is ever stored — only timestamps, token counts, and conversation titles.

---

## Requirements

- **Browser:** Brave or Google Chrome (any Chromium-based browser that supports Manifest V3 extensions)
- **Site:** Works exclusively on [claude.ai](https://claude.ai)
- Microsoft Edge is **not recommended** — Edge's Tracking Prevention blocks the extension's storage access on claude.ai by default

---

## Installation

This extension is loaded as an unpacked extension (it is not published to the Chrome Web Store).

### Step 1 — Open the extensions page

| Browser | Address bar URL |
|---------|----------------|
| Brave   | `brave://extensions` |
| Chrome  | `chrome://extensions` |

### Step 2 — Enable Developer Mode

Toggle **Developer mode** on using the switch in the top-right corner of the extensions page.

### Step 3 — Load the extension

1. Click **Load unpacked**
2. Navigate to and select the `Prompt Report` folder (the folder containing `manifest.json`)
3. Click **Select Folder**

The **prompt.ly** extension will appear in your extensions list with the bar-chart icon.

### Step 4 — Pin the extension (recommended)

Click the puzzle-piece icon in your browser toolbar, find **prompt.ly**, and click the pin icon so it stays visible in the toolbar.

---

## Browser-specific settings

### Brave

Brave Shields do not interfere with this extension. No changes to Brave settings are required.

If you have any issues, verify that Shields are not set to an aggressive blocking mode on claude.ai:
1. Go to `claude.ai`
2. Click the Brave Shields icon (lion) in the address bar
3. Ensure **Trackers & ads blocking** is not set to **Aggressive** — standard blocking is fine

### Google Chrome

No additional settings are required.

### Microsoft Edge (not recommended)

Edge's Tracking Prevention blocks the extension from communicating with its own storage when on claude.ai. If you must use Edge:
1. Go to `edge://settings/privacy`
2. Under **Tracking prevention → Exceptions**, click **Add a site**
3. Add `https://claude.ai`

Even with this workaround, Brave or Chrome are strongly preferred.

---

## Usage

### Viewing your usage summary

Click the **prompt.ly** icon in the browser toolbar to open the popup. It shows:

- **Prompts sent** — total number of messages you have sent
- **Input tokens** — estimated tokens in your messages
- **Output tokens** — estimated tokens in Claude's responses
- **Total tokens** — combined total

### Viewing the full report

Click **View Full Report** in the popup to open the dashboard in a new tab. The report includes:

- Summary stat cards
- **Prompts per day** bar chart
- **Token usage per day** stacked bar chart (input + output)
- **Export CSV** — downloads a spreadsheet of all recorded prompts
- **Clear data** — permanently deletes all stored data

### Resetting the counter

Click **Reset** in the popup (next to "View Full Report") to wipe all stored data immediately. You will be asked to confirm before anything is deleted.

---

## Settings

Click the **⚙** gear icon in the popup (or the **Settings** link in the full report) to open the settings page.

| Setting | Options | Default |
|---------|---------|---------|
| Rolling window | 7 days / 30 days / 90 days | 30 days |

The rolling window controls how far back data is shown and retained. Entries older than the selected window are automatically pruned.

---

## Important notes

- **Refresh required after extension reload:** If you reload the extension from the extensions page, you must also refresh your claude.ai tab for tracking to resume. The extension injects its tracking code when the page loads — a mid-session reload breaks the connection until the page is refreshed.
- **New conversations only:** The extension tracks prompts sent after it is installed and the page is loaded. It cannot retroactively retrieve past conversations.
- **Data is stored locally:** All data is stored in your browser's local extension storage (`chrome.storage.local`). Nothing is sent to any server.

---

## File structure

```
Prompt Report/
├── manifest.json          — Extension configuration
├── background.js          — Service worker (data storage)
├── content-main.js        — Intercepts claude.ai API calls (MAIN world)
├── content-isolated.js    — Bridges page ↔ extension messaging (ISOLATED world)
├── popup.html / popup.js  — Toolbar popup UI
├── report.html / report.js — Full dashboard with charts
├── options.html / options.js — Settings page
├── lib/
│   └── chart.min.js       — Chart.js 4.4.4 (bundled locally)
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```
