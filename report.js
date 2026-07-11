// Resolve color tokens from CSS custom properties (set on :root by the stylesheet)
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function fmt(n) {
  return n.toLocaleString();
}

function fmtCompact(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 10_000)    return (n / 1_000).toFixed(1) + 'k';
  return n.toLocaleString();
}

function dateKey(ts) {
  return new Date(ts).toLocaleDateString('en-CA'); // YYYY-MM-DD
}

function shortLabel(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function groupByDay(prompts) {
  const grouped = {};
  for (const p of prompts) {
    const k = dateKey(p.timestamp);
    if (!grouped[k]) grouped[k] = { inputTokens: 0, outputTokens: 0, count: 0 };
    grouped[k].inputTokens  += p.inputTokens;
    grouped[k].outputTokens += p.outputTokens;
    grouped[k].count        += 1;
  }
  return grouped;
}

function fillDays(grouped, windowDays) {
  const today = new Date();
  const result = [];
  for (let i = windowDays - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const k = dateKey(d.getTime());
    result.push({ date: k, ...(grouped[k] || { inputTokens: 0, outputTokens: 0, count: 0 }) });
  }
  return result;
}

function exportCSV(prompts) {
  const rows = [...prompts]
    .sort((a, b) => a.timestamp - b.timestamp)
    .map(p => {
      const d   = new Date(p.timestamp);
      const date = dateKey(p.timestamp);
      const time = d.toTimeString().slice(0, 8);
      const title = (p.conversationTitle || 'Untitled').replace(/"/g, '""');
      return `${date},${time},"${title}",${p.inputTokens},${p.outputTokens},${p.inputTokens + p.outputTokens}`;
    });

  const csv  = 'Date,Time,Conversation Title,Input Tokens,Output Tokens,Total Tokens\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `prompt-report-${dateKey(Date.now())}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function makeBaseOptions(stacked) {
  const s1      = cssVar('--s1');
  const s2      = cssVar('--s2');
  const muted   = cssVar('--text-muted');
  const sec     = cssVar('--text-sec');
  const grid    = cssVar('--grid');
  const surface = cssVar('--surface');

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    plugins: {
      legend: {
        display: stacked,
        position: 'bottom',
        labels: {
          color: sec,
          usePointStyle: true,
          pointStyle: 'rect',
          pointStyleWidth: 12,
          font: { size: 12, family: 'system-ui, -apple-system, "Segoe UI", sans-serif' },
          padding: 16,
        },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: cssVar('--surface-alt'),
        titleColor: cssVar('--text-pri'),
        bodyColor: sec,
        borderColor: cssVar('--sep'),
        borderWidth: 1,
        padding: 10,
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        stacked: stacked,
        grid: { display: false },
        border: { color: grid },
        ticks: {
          color: muted,
          font: { size: 11 },
          maxTicksLimit: 10,
          maxRotation: 0,
        },
      },
      y: {
        stacked: stacked,
        grid: { color: grid, lineWidth: 1 },
        border: { display: false },
        ticks: {
          color: muted,
          font: { size: 11 },
          callback: v => v.toLocaleString(),
        },
        beginAtZero: true,
      },
    },
  };
}

function loadData() {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'GET_DATA' }, resolve);
  });
}

(async () => {
  const result = await loadData();
  const { prompts = [], settings = { windowDays: 30 } } = result || {};

  // Date range header
  const endDate   = new Date();
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - (settings.windowDays - 1));
  const rangeStr =
    startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
    ' – ' +
    endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  document.getElementById('dateRange').textContent = `Last ${settings.windowDays} days  ·  ${rangeStr}`;

  // Summary cards
  const totalInput  = prompts.reduce((s, p) => s + p.inputTokens, 0);
  const totalOutput = prompts.reduce((s, p) => s + p.outputTokens, 0);
  document.getElementById('statPrompts').textContent = fmt(prompts.length);
  document.getElementById('statInput').textContent   = fmtCompact(totalInput);
  document.getElementById('statOutput').textContent  = fmtCompact(totalOutput);
  document.getElementById('statTotal').textContent   = fmtCompact(totalInput + totalOutput);

  // Empty state
  if (prompts.length === 0) {
    document.getElementById('mainContent').innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <div class="empty-title">No data yet</div>
        <div class="empty-desc">Send some prompts on claude.ai and they'll appear here.</div>
      </div>
    `;
    document.getElementById('exportBtn').disabled = true;
    document.getElementById('clearBtn').disabled  = true;
    return;
  }

  // Day-level data
  const grouped = groupByDay(prompts);
  const days    = fillDays(grouped, settings.windowDays);
  const labels  = days.map(d => shortLabel(d.date));

  const s1 = cssVar('--s1');
  const s2 = cssVar('--s2');
  const surface = cssVar('--surface');

  // Prompts per day chart (single series — no legend, title names it)
  const promptCtx = document.getElementById('promptChart').getContext('2d');
  new Chart(promptCtx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Prompts',
        data: days.map(d => d.count),
        backgroundColor: s1,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: makeBaseOptions(false),
  });

  // Tokens per day chart (stacked: input + output)
  const tokenCtx = document.getElementById('tokenChart').getContext('2d');
  new Chart(tokenCtx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Input tokens',
          data: days.map(d => d.inputTokens),
          backgroundColor: s1,
          borderRadius: { topLeft: 0, topRight: 0, bottomLeft: 4, bottomRight: 4 },
          borderSkipped: false,
          stack: 'tokens',
        },
        {
          label: 'Output tokens',
          data: days.map(d => d.outputTokens),
          backgroundColor: s2,
          borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 },
          borderSkipped: false,
          borderWidth: { bottom: 2 },
          borderColor: surface,
          stack: 'tokens',
        },
      ],
    },
    options: makeBaseOptions(true),
  });

  // Actions
  document.getElementById('exportBtn').addEventListener('click', () => exportCSV(prompts));

  document.getElementById('clearBtn').addEventListener('click', async () => {
    if (!confirm('Clear all stored data? This cannot be undone.')) return;
    await new Promise(resolve => chrome.runtime.sendMessage({ type: 'CLEAR_DATA' }, resolve));
    window.location.reload();
  });

  document.getElementById('settingsLink').addEventListener('click', e => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });
})();
