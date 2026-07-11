window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  if (!event.data || event.data.type !== 'PROMPT_REPORT_DATA') return;
  if (event.data.source !== 'prompt-report-ext') return;

  try {
    chrome.runtime.sendMessage({
      type: 'SAVE_PROMPT',
      payload: event.data.payload,
    });
  } catch (_) {
    // Extension was reloaded; page needs a refresh to reconnect.
  }
});
