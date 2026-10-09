# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal self-contained web chat UI for sunnyware."""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>sunnyware</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #0e1014; color: #e6e8eb; height: 100vh; display: flex; flex-direction: column; }
  header { padding: 12px 20px; border-bottom: 1px solid #1d2026; display: flex;
           justify-content: space-between; align-items: center; background: #121418; }
  header h1 { margin: 0; font-size: 16px; font-weight: 600; color: #ffb454; }
  header .meta { font-size: 12px; color: #6e7480; }
  header a { color: #6e9bd8; text-decoration: none; font-size: 12px; margin-left: 12px; }
  #chat { flex: 1; overflow-y: auto; padding: 20px; max-width: 860px; margin: 0 auto; width: 100%; }
  .msg { margin-bottom: 16px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .msg.user { color: #b8c4d0; }
  .msg.user::before { content: "you: "; color: #ffb454; font-weight: 600; }
  .msg.agent { color: #e6e8eb; }
  .msg.agent::before { content: "sunny: "; color: #52b788; font-weight: 600; }
  .msg.error { color: #ff6b6b; }
  .msg.step { font-size: 12px; color: #6e7480; font-style: italic; padding-left: 48px; }
  footer { padding: 16px 20px; border-top: 1px solid #1d2026; background: #121418; }
  form { max-width: 860px; margin: 0 auto; display: flex; gap: 10px; }
  input[type=text] { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #2a2e36;
                     background: #0e1014; color: #e6e8eb; font-size: 14px; font-family: inherit; }
  input[type=text]:focus { outline: none; border-color: #52b788; }
  button { padding: 12px 24px; border-radius: 8px; border: none; background: #52b788; color: #0e1014;
           font-weight: 600; cursor: pointer; font-size: 14px; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .footer-info { max-width: 860px; margin: 6px auto 0; text-align: right;
                 font-size: 11px; color: #4d5260; }
</style>
</head>
<body>
<header>
  <h1>sunnyware</h1>
  <div class="meta">
    <span id="sid">session: ...</span>
    <a href="/docs" target="_blank">API docs</a>
    <a href="/about" target="_blank">about</a>
    <a href="#" id="clear">new session</a>
  </div>
</header>
<div id="chat"></div>
<footer>
  <form id="form">
    <input type="text" id="input" placeholder="Ask anything..." autocomplete="off" required>
    <button type="submit" id="send">Send</button>
  </form>
  <div class="footer-info">Powered by sunnyware · <span id="latency">—</span></div>
</footer>
<script>
(function () {
  const chat = document.getElementById('chat');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  const sidEl = document.getElementById('sid');
  const latEl = document.getElementById('latency');
  const clearBtn = document.getElementById('clear');

  function getSession() {
    let s = localStorage.getItem('sunnyware_session');
    if (!s) {
      s = 'web-' + Math.random().toString(36).slice(2, 10);
      localStorage.setItem('sunnyware_session', s);
    }
    return s;
  }

  function renderSession() {
    sidEl.textContent = 'session: ' + getSession();
  }

  function addMsg(text, cls) {
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    d.textContent = text;
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
  }

  async function sendMessage(text) {
    addMsg(text, 'user');
    send.disabled = true;
    const thinking = addMsg('thinking...', 'step');
    const t0 = performance.now();
    try {
      const r = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: text, session_id: getSession() }),
      });
      const data = await r.json();
      const ms = Math.round(performance.now() - t0);
      latEl.textContent = ms + ' ms';
      thinking.remove();
      if (data.error) {
        addMsg('error: ' + (data.detail || data.error), 'error');
        return;
      }
      const content = data.result && data.result.content;
      if (content) {
        addMsg(content, 'agent');
      } else {
        addMsg('(empty response)', 'error');
      }
      const steps = (data.result && data.result.steps) || [];
      for (const s of steps) {
        const t = s.tool || '?';
        const proto = s.protocol ? (' (' + s.protocol + ')') : '';
        addMsg('[tool] ' + t + proto, 'step');
      }
    } catch (e) {
      thinking.remove();
      addMsg('network error: ' + e.message, 'error');
    } finally {
      send.disabled = false;
      input.focus();
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendMessage(text);
  });

  clearBtn.addEventListener('click', (e) => {
    e.preventDefault();
    localStorage.removeItem('sunnyware_session');
    chat.innerHTML = '';
    renderSession();
    addMsg('Welcome to sunnyware. Ask me anything.', 'step');
    input.focus();
  });

  // Init
  renderSession();
  addMsg('Welcome to sunnyware. Ask me anything.', 'step');
  input.focus();
})();
</script>
</body>
</html>
"""
