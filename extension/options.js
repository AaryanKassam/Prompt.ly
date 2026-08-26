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

  const captureText = document.getElementById('captureText');
  const backendEnabled = document.getElementById('backendEnabled');
  const backendUrl = document.getElementById('backendUrl');
  captureText.checked = !!settings.captureText;
  backendEnabled.checked = settings.backendEnabled !== false;
  backendUrl.value = settings.backendUrl || 'http://localhost:8000';

  document.getElementById('saveBtn').addEventListener('click', async () => {
    const selected = document.querySelector('input[name="windowDays"]:checked');

    const btn = document.getElementById('saveBtn');
    btn.disabled = true;
    await saveSettings({
      windowDays: selected ? parseInt(selected.value, 10) : settings.windowDays,
      captureText: captureText.checked,
      backendEnabled: backendEnabled.checked,
      backendUrl: backendUrl.value.trim() || 'http://localhost:8000',
    });
    btn.textContent = 'Saved!';
    setTimeout(() => {
      btn.textContent = 'Save';
      btn.disabled = false;
    }, 1500);
  });
})();
