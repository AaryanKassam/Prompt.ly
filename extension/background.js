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

async function savePrompt(data) {
  const stored = await chrome.storage.local.get(['prompts', 'settings']);
  const settings = stored.settings || { windowDays: 30 };
  const prompts = stored.prompts || [];

  const entry = {
    id: crypto.randomUUID(),
    conversationId: data.conversationId || 'unknown',
    conversationTitle: data.conversationTitle || 'Untitled',
    timestamp: data.timestamp || Date.now(),
    inputTokens: data.inputTokens || 0,
    outputTokens: data.outputTokens || 0,
  };

  const cutoff = Date.now() - settings.windowDays * 86_400_000;
  const pruned = prompts.filter(p => p.timestamp >= cutoff);
  pruned.push(entry);

  await chrome.storage.local.set({ prompts: pruned });
}

async function getData() {
  const stored = await chrome.storage.local.get(['prompts', 'settings']);
  const settings = stored.settings || { windowDays: 30 };
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
  return stored.settings || { windowDays: 30 };
}

async function saveSettings(settings) {
  await chrome.storage.local.set({ settings });
  return { ok: true };
}
