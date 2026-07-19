function getSettings() {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, resolve);
  });
}

function saveSettings(settings) {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'SAVE_SETTINGS', payload: settings }, resolve);
  });
}

(async () => {
  const settings = (await getSettings()) || { windowDays: 30 };
  const radios = document.querySelectorAll('input[name="windowDays"]');
  radios.forEach(r => {
    r.checked = parseInt(r.value, 10) === settings.windowDays;
  });

  document.getElementById('saveBtn').addEventListener('click', async () => {
    const selected = document.querySelector('input[name="windowDays"]:checked');
    if (!selected) return;

    const btn = document.getElementById('saveBtn');
    btn.disabled = true;
    await saveSettings({ windowDays: parseInt(selected.value, 10) });
    btn.textContent = 'Saved!';
    setTimeout(() => {
      btn.textContent = 'Save';
      btn.disabled = false;
    }, 1500);
  });
})();
