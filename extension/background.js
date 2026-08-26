chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'SAVE_PROMPT') {
    savePrompt(message.payload);
    return false;
  }
  if (message.type === 'GET_DATA') {
    getData().then(sendResponse);
    return true;
  }
  if (message.type === 'CLEAR_DATA') {
    clearData().then(sendResponse);
    return true;
  }
  if (message.type === 'GET_SETTINGS') {
    getSettings().then(sendResponse);
    return true;
  }
  if (message.type === 'SAVE_SETTINGS') {
    saveSettings(message.payload).then(sendResponse);
    return true;
  }
});

const DEFAULT_SETTINGS = {
  windowDays: 30,
  captureText: false,                    // opt-in: store actual prompt/response text
  backendEnabled: true,                  // POST to the local Prompt.ly backend
  backendUrl: 'http://localhost:8000',
};

async function savePrompt(data) {
  const stored = await chrome.storage.local.get(['prompts', 'settings']);
  const settings = { ...DEFAULT_SETTINGS, ...(stored.settings || {}) };
  const prompts = stored.prompts || [];

  const conversationId = data.conversationId || 'unknown';
  // turnIndex = how many turns we've already recorded for this conversation + 1.
  const turnIndex = prompts.filter(p => p.conversationId === conversationId).length + 1;

  const entry = {
    id: crypto.randomUUID(),
    conversationId,
    conversationTitle: data.conversationTitle || 'Untitled',
    timestamp: data.timestamp || Date.now(),
    inputTokens: data.inputTokens || 0,
    outputTokens: data.outputTokens || 0,
    messageId: data.messageId || null,
    turnIndex,
  };

  // Text is only persisted when the user opts in.
  if (settings.captureText) {
    entry.promptText = data.promptText || '';
    entry.responseText = data.responseText || '';
  }

  const cutoff = Date.now() - settings.windowDays * 86_400_000;
  const pruned = prompts.filter(p => p.timestamp >= cutoff);
  pruned.push(entry);

  await chrome.storage.local.set({ prompts: pruned });

  // Best-effort mirror to the backend. Never let a backend failure break the
  // extension — it must keep working fully offline.
  if (settings.backendEnabled) {
    postToBackend(settings, entry);
  }
}

async function postToBackend(settings, entry) {
  try {
    const payload = {
      conversationId: entry.conversationId,
      conversationTitle: entry.conversationTitle,
      timestamp: new Date(entry.timestamp).toISOString(),
      inputTokens: entry.inputTokens,
      outputTokens: entry.outputTokens,
      messageId: entry.messageId,
      turnIndex: entry.turnIndex,
    };
    // Only send text if it was captured (opt-in).
    if (settings.captureText) {
      payload.promptText = entry.promptText || '';
      payload.responseText = entry.responseText || '';
    }
    await fetch(`${settings.backendUrl}/api/ingest/browser`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (_) {
    // Backend offline — no-op.
  }
}

async function getData() {
  const stored = await chrome.storage.local.get(['prompts', 'settings']);
  const settings = { ...DEFAULT_SETTINGS, ...(stored.settings || {}) };
  const prompts = stored.prompts || [];
  const cutoff = Date.now() - settings.windowDays * 86_400_000;
  return { prompts: prompts.filter(p => p.timestamp >= cutoff), settings };
}

async function clearData() {
  await chrome.storage.local.set({ prompts: [] });
  return { ok: true };
}

async function getSettings() {
  const stored = await chrome.storage.local.get('settings');
  return { ...DEFAULT_SETTINGS, ...(stored.settings || {}) };
}

async function saveSettings(settings) {
  const stored = await chrome.storage.local.get('settings');
  const merged = { ...DEFAULT_SETTINGS, ...(stored.settings || {}), ...settings };
  await chrome.storage.local.set({ settings: merged });
  return { ok: true };
}
