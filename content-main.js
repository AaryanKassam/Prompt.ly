(function () {
  'use strict';

  function estimate(text) {
    if (!text || typeof text !== 'string') return 0;
    return Math.ceil(text.length / 4);
  }

  function isCompletionURL(url) {
    return (
      (url.includes('/chat_conversations/') && url.includes('/completion')) ||
      url.includes('/append_message')
    );
  }

  function extractConvId(url) {
    const m = url.match(/chat_conversations\/([^/?#]+)/);
    return m ? m[1] : 'unknown';
  }

  function estimateInputTokens(bodyStr) {
    if (!bodyStr) return 0;
    try {
      const body = JSON.parse(bodyStr);

      if (typeof body.prompt === 'string') {
        return estimate(body.prompt);
      }

      if (Array.isArray(body.messages)) {
        const userMsgs = body.messages.filter(m => m.role === 'user');
        const last = userMsgs[userMsgs.length - 1];
        if (last) {
          const text = Array.isArray(last.content)
            ? last.content.filter(c => c.type === 'text').map(c => c.text).join(' ')
            : String(last.content || '');
          return estimate(text);
        }
      }

      return Math.ceil(JSON.stringify(body).length / 10);
    } catch (_) {
      return estimate(String(bodyStr));
    }
  }

  function parseSSEText(text) {
    let deltaText = '';
    let lastCompletion = '';
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const raw = trimmed.slice(6);
      if (raw === '[DONE]') continue;
      try {
        const ev = JSON.parse(raw);
        if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') {
          deltaText += ev.delta.text || '';
        }
        if (typeof ev.completion === 'string') lastCompletion = ev.completion;
        if (!ev.type && ev.delta?.text) deltaText += ev.delta.text;
      } catch (_) {}
    }
    const out = deltaText.length >= lastCompletion.length ? deltaText : lastCompletion;
    return estimate(out);
  }

  function postData(conversationId, inputTokens, outputTokens) {
    const conversationTitle = document.title
      .replace(/\s*[-|]\s*Claude\s*$/, '').trim() || 'Untitled';
    window.postMessage(
      {
        type:    'PROMPT_REPORT_DATA',
        source:  'prompt-report-ext',
        payload: { conversationId, conversationTitle, timestamp: Date.now(), inputTokens, outputTokens },
      },
      '*'
    );
  }

  // ── XHR interception ───────────────────────────────────────────────────────
  const _XHROpen = XMLHttpRequest.prototype.open;
  const _XHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._prUrl    = String(url);
    this._prMethod = String(method).toUpperCase();
    return _XHROpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function (body) {
    if (this._prUrl && isCompletionURL(this._prUrl)) {
      const inputTokens    = estimateInputTokens(typeof body === 'string' ? body : '');
      const conversationId = extractConvId(this._prUrl);
      const handler = () => {
        this.removeEventListener('loadend', handler);
        postData(conversationId, inputTokens, parseSSEText(this.responseText || ''));
      };
      this.addEventListener('loadend', handler);
    }
    return _XHRSend.apply(this, [body]);
  };

  // ── Fetch interception ─────────────────────────────────────────────────────
  const _originalFetch = window.fetch;

  window.fetch = async function (...args) {
    const [resource, config] = args;
    const url =
      typeof resource === 'string'
        ? resource
        : resource instanceof Request
        ? resource.url
        : String(resource);

    if (!isCompletionURL(url)) {
      return _originalFetch.apply(this, args);
    }

    let bodyStr = '';
    if (config?.body && typeof config.body === 'string') {
      bodyStr = config.body;
    } else if (resource instanceof Request) {
      try { bodyStr = await resource.clone().text(); } catch (_) {}
    }

    const inputTokens    = estimateInputTokens(bodyStr);
    const conversationId = extractConvId(url);
    const response       = await _originalFetch.apply(this, args);

    if (response.body) {
      // Tee before returning so our reader is independent of any abort the page issues.
      const [forPage, forUs] = response.body.tee();
      const decoder = new TextDecoder();
      let accumulated = '';

      (async () => {
        const reader = forUs.getReader();
        try {
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            accumulated += decoder.decode(value, { stream: true });
          }
          accumulated += decoder.decode();
          postData(conversationId, inputTokens, parseSSEText(accumulated));
        } catch (_) {
          if (accumulated.length > 0) {
            postData(conversationId, inputTokens, parseSSEText(accumulated));
          }
        }
      })();

      return new Response(forPage, {
        status:     response.status,
        statusText: response.statusText,
        headers:    response.headers,
      });
    }

    response.clone().text().then(text => {
      postData(conversationId, inputTokens, parseSSEText(text));
    }).catch(() => {});

    return response;
  };
})();
