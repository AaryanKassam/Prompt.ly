function fmt(n) {
  return n.toLocaleString();
}

function loadData() {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'GET_DATA' }, resolve);
  });
}

(async () => {
  const result = await loadData();
  const { prompts = [], settings = { windowDays: 30 } } = result || {};

  document.getElementById('period').textContent = `Last ${settings.windowDays} days`;

  const totalInput  = prompts.reduce((s, p) => s + p.inputTokens, 0);
  const totalOutput = prompts.reduce((s, p) => s + p.outputTokens, 0);

  const statsEl = document.getElementById('stats');

  if (prompts.length === 0) {
    statsEl.innerHTML = '<div class="empty">No data yet.<br>Start chatting on claude.ai!</div>';
  } else {
    statsEl.innerHTML = `
      <div class="stat-row">
        <span class="stat-label">Prompts sent</span>
        <span class="stat-value">${fmt(prompts.length)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Input tokens</span>
        <span class="stat-value">${fmt(totalInput)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Output tokens</span>
        <span class="stat-value">${fmt(totalOutput)}</span>
      </div>
      <div class="stat-row total">
        <span class="stat-label">Total tokens</span>
        <span class="stat-value">${fmt(totalInput + totalOutput)}</span>
      </div>
    `;
  }

  document.getElementById('reportBtn').addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('report.html') });
    window.close();
  });

  document.getElementById('settingsBtn').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
    window.close();
  });

  document.getElementById('resetBtn').addEventListener('click', async () => {
    if (!confirm('Clear all stored data? This cannot be undone.')) return;
    await new Promise(resolve => chrome.runtime.sendMessage({ type: 'CLEAR_DATA' }, resolve));
    window.location.reload();
  });
})();
