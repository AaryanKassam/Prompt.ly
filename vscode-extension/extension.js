/**
 * Prompt.ly for VS Code.
 *
 * Renders the prompt-quality report for the folder currently open in the editor
 * as a sidebar view, and can score selected text as a draft prompt.
 *
 * The extension owns no scoring logic of its own: it shells out to the repo's
 * `promptly` CLI with `--json`, which is the same code path the terminal UI and
 * the Claude MCP extension use. One scoring engine, three front-ends — they can
 * never disagree about what a prompt is worth.
 *
 * Plain JavaScript on purpose: no compile step, so the folder can be symlinked
 * straight into ~/.vscode/extensions and reloaded.
 */
const vscode = require("vscode");
const { execFile } = require("child_process");
const fs = require("fs");
const path = require("path");

const CLI_TIMEOUT_MS = 60_000;

/** Locate the `promptly` launcher: explicit setting, then alongside this folder. */
function resolveCli() {
  const configured = vscode.workspace.getConfiguration("promptly").get("cliPath");
  if (configured) return configured;

  // __dirname is <repo>/vscode-extension when installed via symlink or clone.
  const candidates = [
    path.join(__dirname, "..", "scripts", "promptly"),
    path.join(fs.realpathSync(__dirname), "..", "scripts", "promptly"),
  ];
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch {
      /* keep looking */
    }
  }
  return null;
}

/** Run a promptly subcommand and parse its JSON output. */
function runCli(args, cwd) {
  return new Promise((resolve, reject) => {
    const cli = resolveCli();
    if (!cli) {
      reject(new Error("NO_CLI"));
      return;
    }
    execFile(
      cli,
      args,
      { cwd, timeout: CLI_TIMEOUT_MS, maxBuffer: 8 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          reject(new Error(stderr.trim() || err.message));
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error(`Unexpected CLI output: ${stdout.slice(0, 200)}`));
        }
      },
    );
  });
}

function activeFolder() {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return null;

  // With a multi-root workspace, follow the file the user is actually editing.
  const activeUri = vscode.window.activeTextEditor?.document.uri;
  if (activeUri) {
    const owner = vscode.workspace.getWorkspaceFolder(activeUri);
    if (owner) return owner.uri.fsPath;
  }
  return folders[0].uri.fsPath;
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

/** Shared 0-10 colour scale, expressed with VS Code's own theme tokens. */
function toneVar(score) {
  if (score === null || score === undefined) return "var(--vscode-descriptionForeground)";
  if (score < 5) return "var(--vscode-charts-red)";
  if (score < 7) return "var(--vscode-charts-yellow)";
  return "var(--vscode-charts-green)";
}

function styles() {
  return `
    :root { color-scheme: inherit; }
    body {
      padding: 10px 12px;
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
    }
    .muted { color: var(--vscode-descriptionForeground); }
    .eyebrow {
      text-transform: uppercase; letter-spacing: .06em; font-size: 10px;
      color: var(--vscode-descriptionForeground); margin: 16px 0 6px;
    }
    .eyebrow:first-child { margin-top: 0; }
    .score { font-size: 30px; font-weight: 600; line-height: 1; font-variant-numeric: tabular-nums; }
    .grade { font-size: 13px; margin-left: 6px; color: var(--vscode-descriptionForeground); }
    .sub { margin-top: 4px; font-size: 11px; color: var(--vscode-descriptionForeground); }
    .factor { display: grid; grid-template-columns: 74px 1fr 26px; gap: 8px; align-items: center; margin-bottom: 5px; }
    .factor span:first-child { text-transform: capitalize; font-size: 11px; color: var(--vscode-descriptionForeground); }
    .track { height: 5px; border-radius: 3px; background: var(--vscode-editorWidget-background); overflow: hidden; }
    .fill { height: 100%; border-radius: 3px; }
    .val { text-align: right; font-size: 11px; font-variant-numeric: tabular-nums; color: var(--vscode-descriptionForeground); }
    .rec { display: flex; gap: 8px; padding: 7px 0; border-top: 1px solid var(--vscode-editorWidget-border, rgba(128,128,128,.2)); }
    .rec:first-of-type { border-top: none; }
    .pct { font-variant-numeric: tabular-nums; font-weight: 600; font-size: 11px;
           color: var(--vscode-charts-yellow); min-width: 30px; }
    .rec p { margin: 0; font-size: 12px; line-height: 1.45; }
    .prompt { display: flex; gap: 8px; padding: 6px 0; font-size: 11px; }
    .prompt .s { font-variant-numeric: tabular-nums; font-weight: 600; min-width: 22px; }
    .tokens { display: flex; gap: 10px; margin-bottom: 4px; }
    .tokens > div { flex: 1; min-width: 0; }
    .tokens b { display: block; font-size: 14px; font-variant-numeric: tabular-nums; }
    .tokens span { display: block; font-size: 10px; color: var(--vscode-descriptionForeground);
                   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .prompt .t { color: var(--vscode-descriptionForeground); line-height: 1.4; }
    button {
      width: 100%; margin-top: 14px; padding: 6px 10px; cursor: pointer;
      border: none; border-radius: 3px; font-family: inherit; font-size: 12px;
      background: var(--vscode-button-background); color: var(--vscode-button-foreground);
    }
    button:hover { background: var(--vscode-button-hoverBackground); }
    button.secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground); margin-top: 6px;
    }
    code { font-family: var(--vscode-editor-font-family); font-size: 11px; }
    .empty { padding: 18px 0; font-size: 12px; line-height: 1.5; }
    details { margin-top: 8px; font-size: 11px; color: var(--vscode-descriptionForeground); }
    details summary { cursor: pointer; }
    details pre { white-space: pre-wrap; word-break: break-word; margin: 6px 0 0;
                  font-family: var(--vscode-editor-font-family); font-size: 10px; }
    .skeleton { height: 9px; border-radius: 3px; background: var(--vscode-editorWidget-background);
                margin-bottom: 8px; animation: pulse 1.4s ease-in-out infinite; }
    @keyframes pulse { 0%,100% { opacity: .45 } 50% { opacity: .9 } }
    @media (prefers-reduced-motion: reduce) { .skeleton { animation: none } }
  `;
}

function shell(bodyHtml) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy"
          content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
    <style>${styles()}</style></head>
    <body>${bodyHtml}
    <script>
      const vscode = acquireVsCodeApi();
      document.querySelectorAll('[data-cmd]').forEach((el) => {
        el.addEventListener('click', () => vscode.postMessage({ command: el.dataset.cmd }));
      });
    </script></body></html>`;
}

function loadingHtml() {
  return shell(
    `<div class="eyebrow">Loading</div>` +
      `<div class="skeleton" style="width:55%;height:22px"></div>` +
      Array.from({ length: 6 }, () => `<div class="skeleton"></div>`).join(""),
  );
}

function errorHtml(message) {
  const noCli = message === "NO_CLI";

  // Python tracebacks put the useful line last; leading a webview with 20 lines
  // of stack tells the reader nothing, so summarise and tuck the rest away.
  const lines = String(message).split("\n").filter((l) => l.trim());
  const summary = lines.length ? lines[lines.length - 1] : "Unknown error";
  const hasDetail = lines.length > 1;

  return shell(
    `<div class="eyebrow">Prompt.ly</div>
     <div class="empty">
       ${
         noCli
           ? `Couldn't find the <code>promptly</code> CLI. Set <code>promptly.cliPath</code>
              in settings to the full path of <code>scripts/promptly</code> in your Prompt.ly checkout.`
           : escapeHtml(summary)
       }
     </div>
     ${
       hasDetail && !noCli
         ? `<details><summary>Details</summary><pre>${escapeHtml(message)}</pre></details>`
         : ""
     }
     <button data-cmd="refresh">Try again</button>
     ${noCli ? `<button class="secondary" data-cmd="settings">Open settings</button>` : ""}`,
  );
}

function compactNum(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
}

function reportHtml(report) {
  const t = report.totals;
  if (!t || t.prompts === 0) {
    return shell(
      `<div class="eyebrow">${escapeHtml(
        (report.project_path || "").split("/").filter(Boolean).pop() || "This folder",
      )}</div>
       <div class="empty">
         No prompts recorded here yet. Use Claude Code in this folder — the report
         fills in automatically once a session ends.
       </div>
       <button data-cmd="sync">Import sessions now</button>`,
    );
  }

  const factors = Object.entries(report.factors || {})
    .filter(([, v]) => v !== null)
    .map(
      ([name, v]) => `
      <div class="factor">
        <span>${escapeHtml(name)}</span>
        <div class="track"><div class="fill" style="width:${(v / 10) * 100}%;background:${toneVar(v)}"></div></div>
        <span class="val">${v.toFixed(1)}</span>
      </div>`,
    )
    .join("");

  const econ = report.token_economics || {};
  const tokens = econ.prompts_with_tokens
    ? `<div class="eyebrow">Token cost</div>
       <div class="tokens">
         <div><b>${compactNum(econ.total_tokens)}</b><span>total</span></div>
         <div><b>${compactNum(econ.median_output_per_prompt)}</b><span>median reply</span></div>
         <div><b>${compactNum(econ.output_per_file_changed)}</b><span>per file</span></div>
       </div>`
    : "";

  const trend = report.trend
    ? `<span style="color:${
        report.trend.direction === "improving"
          ? "var(--vscode-charts-green)"
          : report.trend.direction === "declining"
            ? "var(--vscode-charts-red)"
            : "var(--vscode-descriptionForeground)"
      }">${
        { improving: "▲", declining: "▼", flat: "▬" }[report.trend.direction]
      } ${escapeHtml(report.trend.direction)}</span> · `
    : "";

  const recs = (report.recommendations || [])
    .slice(0, 4)
    .map(
      (r) => `<div class="rec">
                <span class="pct">${r.missed_pct}%</span>
                <p>${escapeHtml(r.advice)}</p>
              </div>`,
    )
    .join("");

  const worst = (report.worst_prompts || [])
    .map(
      (p) => `<div class="prompt">
                <span class="s" style="color:${toneVar(p.score)}">${p.score.toFixed(1)}</span>
                <span class="t">${escapeHtml(p.preview)}</span>
              </div>`,
    )
    .join("");

  return shell(
    `<div class="score" style="color:${toneVar(report.overall)}">
       ${report.overall === null ? "—" : report.overall.toFixed(1)}<span class="grade">${escapeHtml(report.grade)}</span>
     </div>
     <div class="sub">${trend}${t.scored_prompts} prompts · ${t.sessions} session${t.sessions === 1 ? "" : "s"}</div>

     <div class="eyebrow">Factors</div>${factors}

     ${tokens}

     ${recs ? `<div class="eyebrow">Do these next</div>${recs}` : ""}
     ${worst ? `<div class="eyebrow">Lowest-scoring prompts</div>${worst}` : ""}

     <button data-cmd="refresh">Refresh</button>
     <button class="secondary" data-cmd="dashboard">Open full dashboard</button>`,
  );
}

class ReportViewProvider {
  constructor(context, statusBar) {
    this.context = context;
    this.statusBar = statusBar;
    this.view = null;
    this.timer = null;
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.command === "refresh") await this.refresh(true);
      else if (msg.command === "sync") await this.sync();
      else if (msg.command === "dashboard") openDashboard();
      else if (msg.command === "settings") {
        vscode.commands.executeCommand("workbench.action.openSettings", "promptly.cliPath");
      }
    });

    // Only poll while the view is actually visible.
    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) this.refresh();
      else this.stopTimer();
    });
    webviewView.onDidDispose(() => this.stopTimer());

    this.refresh();
  }

  stopTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  startTimer() {
    this.stopTimer();
    const seconds = vscode.workspace.getConfiguration("promptly").get("autoRefreshSeconds", 120);
    if (seconds > 0) {
      this.timer = setInterval(() => this.refresh(), seconds * 1000);
    }
  }

  async refresh(force = false) {
    if (!this.view) return;
    const folder = activeFolder();
    if (!folder) {
      this.view.webview.html = shell(
        `<div class="empty">Open a folder to see its prompt report.</div>`,
      );
      return;
    }

    if (force) this.view.webview.html = loadingHtml();

    try {
      const args = ["report", folder, "--json"];
      if (force) args.push("--refresh");
      const report = await runCli(args, folder);
      this.view.webview.html = reportHtml(report);
      this.updateStatusBar(report);
      this.startTimer();
    } catch (err) {
      this.view.webview.html = errorHtml(err.message);
      this.stopTimer();
    }
  }

  async sync() {
    const folder = activeFolder();
    if (!folder) return;
    this.view.webview.html = loadingHtml();
    try {
      await runCli(["sync", "--json"], folder);
    } catch {
      /* refresh reports the failure */
    }
    await this.refresh();
  }

  updateStatusBar(report) {
    const cfg = vscode.workspace.getConfiguration("promptly");
    if (!cfg.get("showStatusBar", true) || report.overall === null) {
      this.statusBar.hide();
      return;
    }
    this.statusBar.text = `$(graph) ${report.overall.toFixed(1)}`;
    this.statusBar.tooltip = `Prompt.ly — ${report.grade}, ${report.totals.scored_prompts} prompts scored in this project`;
    this.statusBar.command = "promptly.focusView";
    this.statusBar.show();
  }
}

function openDashboard() {
  const url = vscode.workspace.getConfiguration("promptly").get("dashboardUrl");
  vscode.env.openExternal(vscode.Uri.parse(url));
}

/** Score whatever the user has selected, as if it were a prompt. */
async function scoreSelection() {
  const editor = vscode.window.activeTextEditor;
  const text = editor?.document.getText(editor.selection);
  if (!text || !text.trim()) {
    vscode.window.showInformationMessage("Select some text to score it as a prompt.");
    return;
  }

  try {
    const result = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Scoring prompt…" },
      () => runCli(["score", text, "--json"], activeFolder() || undefined),
    );

    const weakest = Object.entries(result.factors).sort((a, b) => a[1] - b[1])[0];
    const choice = await vscode.window.showInformationMessage(
      `Prompt score ${result.overall.toFixed(1)}/10 (${result.grade}) — weakest: ${weakest[0]} ${weakest[1].toFixed(1)}`,
      "Show details",
    );
    if (choice === "Show details") {
      const doc = await vscode.workspace.openTextDocument({
        language: "markdown",
        content: renderScoreMarkdown(text, result),
      });
      vscode.window.showTextDocument(doc, { preview: true });
    }
  } catch (err) {
    vscode.window.showErrorMessage(
      err.message === "NO_CLI"
        ? "Prompt.ly: set `promptly.cliPath` to your scripts/promptly path."
        : `Prompt.ly: ${err.message}`,
    );
  }
}

function renderScoreMarkdown(text, result) {
  const lines = [
    `# Prompt score: ${result.overall.toFixed(1)}/10 (${result.grade})`,
    "",
    "## Factors",
    "",
  ];
  for (const [name, value] of Object.entries(result.factors).sort((a, b) => a[1] - b[1])) {
    const filled = Math.round(value);
    lines.push(`- \`${"█".repeat(filled)}${"░".repeat(10 - filled)}\` **${name}** ${value.toFixed(1)}/10`);
  }

  const missed = [];
  for (const [factor, signals] of Object.entries(result.signals || {})) {
    for (const [name, hit] of Object.entries(signals)) {
      if (!hit) missed.push(`${factor}.${name}`.replace(/_/g, " "));
    }
  }
  if (missed.length) {
    lines.push("", "## Missing signals", "", ...missed.map((m) => `- ${m}`));
  }
  lines.push("", "---", "", "## The prompt", "", "```text", text, "```");
  return lines.join("\n");
}

function activate(context) {
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 90);
  const provider = new ReportViewProvider(context, statusBar);

  context.subscriptions.push(
    statusBar,
    vscode.window.registerWebviewViewProvider("promptly.report", provider),
    vscode.commands.registerCommand("promptly.refresh", () => provider.refresh(true)),
    vscode.commands.registerCommand("promptly.sync", () => provider.sync()),
    vscode.commands.registerCommand("promptly.openDashboard", openDashboard),
    vscode.commands.registerCommand("promptly.scoreSelection", scoreSelection),
    vscode.commands.registerCommand("promptly.focusView", () =>
      vscode.commands.executeCommand("promptly.report.focus"),
    ),
    // Switching projects in a multi-root workspace should re-target the report.
    vscode.window.onDidChangeActiveTextEditor(() => provider.refresh()),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
