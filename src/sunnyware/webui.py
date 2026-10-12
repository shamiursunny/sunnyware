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
  #fileInput { display: none; }
  .msg.upload { color: #ffb454; font-size: 13px; }
  .msg.upload-ok { color: #52b788; font-size: 13px; }
  .msg.upload-err { color: #ff6b6b; font-size: 13px; }
  .badge { background: #1d2026; color: #b8c4d0; padding: 2px 8px;
           border-radius: 10px; font-size: 11px; margin-left: 8px; }
  /* Part 35: sidebar layout */
  #layout { display: flex; flex: 1; overflow: hidden; }
  #sidebar { width: 240px; min-width: 240px; background: #0a0c0f;
             border-right: 1px solid #1d2026; display: flex;
             flex-direction: column; overflow: hidden; }
  #sidebar .hdr { padding: 10px 12px; border-bottom: 1px solid #1d2026; }
  #newChatBtn { width: 100%; padding: 8px 12px; background: #1d2026;
                color: #e6e8eb; border: 1px solid #2a2e36;
                border-radius: 6px; cursor: pointer; font-size: 13px;
                text-align: left; font-family: inherit; }
  #newChatBtn:hover { background: #252932; border-color: #52b788; }
  #sessionList { flex: 1; overflow-y: auto; padding: 4px 0; }
  .sess { padding: 8px 14px; cursor: pointer; font-size: 12px;
          color: #b8c4d0; border-left: 3px solid transparent;
          display: flex; justify-content: space-between;
          align-items: center; gap: 6px; }
  .sess:hover { background: #121418; }
  .sess.active { background: #121418; border-left-color: #52b788;
                 color: #e6e8eb; }
  .sess .title { flex: 1; overflow: hidden; text-overflow: ellipsis;
                 white-space: nowrap; }
  .sess .del { opacity: 0; color: #6e7480; font-size: 14px;
               padding: 0 4px; cursor: pointer; }
  .sess:hover .del { opacity: 1; }
  .sess .del:hover { color: #ff6b6b; }
  #main { flex: 1; display: flex; flex-direction: column;
          overflow: hidden; }
  @media (max-width: 720px) { #sidebar { display: none; } }
</style>
</head>
<body>
<header>
  <h1>sunnyware</h1>
  <div class="meta">
    <span id="sid">session: ...</span>
    <a href="/docs" target="_blank">API docs</a>
    <a href="/about" target="_blank">about</a>
    <a href="#" id="upload">\U0001F4CE upload</a>
    <a href="#" id="clear">new session</a>
    <span class="badge" id="docCount">docs: \u2014</span>
    <span class="badge" id="providerBadge" title="Last LLM provider that served a response">via \u2014</span>
  </div>
</header>
<input type="file" id="fileInput" multiple
       accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls">
<div id="layout">
  <aside id="sidebar">
    <div class="hdr">
      <button id="newChatBtn" type="button">+ New chat</button>
    </div>
    <div id="sessionList"></div>
  </aside>
  <div id="main">
    <div id="chat"></div>
    <footer>
      <form id="form">
        <input type="text" id="input" placeholder="Ask anything..." autocomplete="off" required>
        <button type="submit" id="send">Send</button>
      </form>
      <div class="footer-info">Powered by sunnyware · <span id="latency">—</span></div>
    </footer>
  </div>
</div>
<script>
(function () {
  const chat = document.getElementById('chat');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  const sidEl = document.getElementById('sid');
  const latEl = document.getElementById('latency');
  const clearBtn = document.getElementById('clear');

  // Part 35: multi-session storage
  const SESS_KEY = 'sunnyware_sessions_v2';
  const ACTIVE_KEY = 'sunnyware_active_v2';
  const MAX_SESSIONS = 20;
  const MAX_MSGS_PER = 200;

  function getSessions() {
    try {
      const raw = localStorage.getItem(SESS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveSessions(sessions) {
    try {
      // Cap to MAX_SESSIONS by newest first
      const ids = Object.keys(sessions);
      if (ids.length > MAX_SESSIONS) {
        ids.sort((a, b) => (sessions[b].created || 0) - (sessions[a].created || 0));
        const keep = new Set(ids.slice(0, MAX_SESSIONS));
        const trimmed = {};
        for (const k of Object.keys(sessions)) {
          if (keep.has(k)) trimmed[k] = sessions[k];
        }
        sessions = trimmed;
      }
      localStorage.setItem(SESS_KEY, JSON.stringify(sessions));
    } catch (e) { /* quota or json error — ignore */ }
  }

  function getActiveId() {
    return localStorage.getItem(ACTIVE_KEY) || '';
  }

  function setActiveId(id) {
    if (id) localStorage.setItem(ACTIVE_KEY, id);
    else localStorage.removeItem(ACTIVE_KEY);
  }

  function getActiveSession() {
    const id = getActiveId();
    if (!id) return null;
    const s = getSessions();
    return s[id] || null;
  }

  function makeId() {
    return 'web-' + Math.random().toString(36).slice(2, 10);
  }

  function getSession() {
    let id = getActiveId();
    if (!id) {
      id = makeId();
      setActiveId(id);
    }
    return id;
  }

  function ensureSession() {
    const id = getSession();
    const sessions = getSessions();
    if (!sessions[id]) {
      sessions[id] = {
        id: id,
        title: 'New chat',
        created: Date.now(),
        messages: []
      };
      saveSessions(sessions);
    }
    return sessions[id];
  }

  function persistMessage(role, text) {
    if (!text) return;
    const id = getSession();
    const sessions = getSessions();
    if (!sessions[id]) {
      sessions[id] = {
        id: id,
        title: 'New chat',
        created: Date.now(),
        messages: []
      };
    }
    const sess = sessions[id];
    sess.messages.push({ role: role, text: text, ts: Date.now() });
    if (sess.messages.length > MAX_MSGS_PER) {
      sess.messages = sess.messages.slice(-MAX_MSGS_PER);
    }
    // Auto-title from first user message
    if (sess.title === 'New chat' && role === 'user' && text) {
      sess.title = text.length > 40 ? text.slice(0, 40) + '...' : text;
    }
    saveSessions(sessions);
  }

  function renderSession() {
    sidEl.textContent = 'session: ' + getSession();
  }

  function loadSession(id) {
    if (!id) return;
    const sessions = getSessions();
    const sess = sessions[id];
    if (!sess) return;
    setActiveId(id);
    renderSession();
    chat.innerHTML = '';
    if (!sess.messages || sess.messages.length === 0) {
      addMsg('Welcome to sunnyware. Ask me anything.', 'step', false);
    } else {
      for (const m of sess.messages) {
        addMsg(m.text, m.role, false);
      }
    }
    renderSidebar();
    input.focus();
  }

  function renderSidebar() {
    const list = document.getElementById('sessionList');
    if (!list) return;
    const sessions = getSessions();
    const activeId = getActiveId();
    const items = Object.values(sessions)
      .filter(s => s.messages && s.messages.length > 0)
      .sort((a, b) => (b.created || 0) - (a.created || 0));

    list.innerHTML = '';
    for (const s of items) {
      const row = document.createElement('div');
      row.className = 'sess' + (s.id === activeId ? ' active' : '');
      row.dataset.id = s.id;

      const title = document.createElement('span');
      title.className = 'title';
      title.textContent = s.title || 'New chat';
      row.appendChild(title);

      const del = document.createElement('span');
      del.className = 'del';
      del.textContent = '\u00d7';
      del.title = 'Delete';
      del.addEventListener('click', (ev) => {
        ev.stopPropagation();
        deleteSession(s.id);
      });
      row.appendChild(del);

      row.addEventListener('click', () => loadSession(s.id));
      list.appendChild(row);
    }
  }

  function createNewSession() {
    const id = makeId();
    setActiveId(id);
    const sessions = getSessions();
    sessions[id] = {
      id: id,
      title: 'New chat',
      created: Date.now(),
      messages: []
    };
    saveSessions(sessions);
    chat.innerHTML = '';
    renderSession();
    addMsg('Welcome to sunnyware. Ask me anything.', 'step', false);
    renderSidebar();
    input.focus();
  }

  function deleteSession(id) {
    const sessions = getSessions();
    if (!sessions[id]) return;
    delete sessions[id];
    saveSessions(sessions);
    if (getActiveId() === id) {
      const remaining = Object.values(sessions)
        .filter(s => s.messages && s.messages.length > 0)
        .sort((a, b) => (b.created || 0) - (a.created || 0));
      if (remaining.length > 0) {
        loadSession(remaining[0].id);
      } else {
        createNewSession();
      }
    } else {
      renderSidebar();
    }
  }

  function addMsg(text, cls, persist) {
    if (persist === undefined) persist = true;
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    d.textContent = text;
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    if (persist && (cls === 'user' || cls === 'agent' || cls === 'error')) {
      try { persistMessage(cls, text); } catch (e) { /* ignore */ }
    }
    return d;
  }

  async function sendMessage(text) {
    addMsg(text, 'user');
    send.disabled = true;
    const t0 = performance.now();
    let agentBubble = null;
    let agentText = '';

    function ensureBubble() {
      if (!agentBubble) {
        agentBubble = document.createElement('div');
        agentBubble.className = 'msg agent';
        // Insert a blinking cursor until first token arrives
        agentBubble.textContent = '';
        chat.appendChild(agentBubble);
        chat.scrollTop = chat.scrollHeight;
      }
      return agentBubble;
    }

    try {
      const r = await fetch('/api/agent/run/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: text, session_id: getSession() }),
      });

      if (!r.ok) {
        const errText = await r.text();
        addMsg('error: HTTP ' + r.status + ' ' + errText.slice(0, 200), 'error');
        return;
      }

      const reader = r.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });

        // SSE events are separated by blank lines
        const events = buffer.split('\\n\\n');
        buffer = events.pop() || '';

        for (const evt of events) {
          const lines = evt.split('\\n');
          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trim();
            if (!payload) continue;
            let data;
            try {
              data = JSON.parse(payload);
            } catch (e) {
              continue;
            }
            const type = data.type || '';
            if (type === 'content') {
              const piece = data.text || '';
              if (piece) {
                agentText += piece;
                ensureBubble().textContent = agentText;
                chat.scrollTop = chat.scrollHeight;
              }
            } else if (type === 'answer') {
              const ans = data.text || '';
              if (ans) {
                agentText = ans;
                ensureBubble().textContent = agentText;
                chat.scrollTop = chat.scrollHeight;
              }
            } else if (type === 'tool_call') {
              const toolName = data.tool || '?';
              const proto = data.protocol ? (' (' + data.protocol + ')') : '';
              addMsg('[tool] ' + toolName + proto, 'step');
            } else if (type === 'error') {
              addMsg('error: ' + (data.error || data.text || 'unknown'), 'error');
            } else if (type === 'done') {
              if (data.provider) {
                const pb = document.getElementById('providerBadge');
                if (pb) pb.textContent = 'via ' + data.provider;
              }
            }
          }
        }
      }

      const ms = Math.round(performance.now() - t0);
      latEl.textContent = ms + ' ms';

      if (!agentText) {
        addMsg('(empty response)', 'error');
      } else {
        // Part 35: persist the final streamed answer
        try { persistMessage('agent', agentText); } catch (e) { /* ignore */ }
        renderSidebar();
      }
    } catch (e) {
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
    createNewSession();
  });

  // Part 35: new chat button in sidebar
  const newChatBtn = document.getElementById('newChatBtn');
  if (newChatBtn) {
    newChatBtn.addEventListener('click', (e) => {
      e.preventDefault();
      createNewSession();
    });
  }

  // Part 31H: file upload
  const fileInput = document.getElementById('fileInput');
  const uploadLink = document.getElementById('upload');
  const docCountEl = document.getElementById('docCount');

  async function refreshDocCount() {
    try {
      const r = await fetch('/api/rag/status');
      const d = await r.json();
      docCountEl.textContent = 'docs: ' + (d.count || 0);
    } catch (e) {
      docCountEl.textContent = 'docs: \u2014';
    }
  }

  uploadLink.addEventListener('click', (e) => {
    e.preventDefault();
    fileInput.click();
  });

  fileInput.addEventListener('change', async () => {
    const files = Array.from(fileInput.files || []);
    if (files.length === 0) return;

    const total = files.length;
    addMsg('uploading ' + total + ' file' + (total > 1 ? 's' : '') + '...', 'upload');

    let okCount = 0;
    let failCount = 0;
    let totalChunks = 0;

    for (let i = 0; i < total; i++) {
      const f = files[i];
      const idx = (i + 1) + '/' + total;
      addMsg('  [' + idx + '] ' + f.name + ' (' + Math.round(f.size/1024) + ' KB)...', 'upload');
      const formData = new FormData();
      formData.append('file', f);
      try {
        const r = await fetch('/api/rag/upload', { method: 'POST', body: formData });
        const d = await r.json();
        if (d.ok) {
          okCount++;
          totalChunks += d.chunks_added || 0;
          addMsg('  \u2713 ' + d.filename + ' \u2014 ' + d.chunks_added +
                 ' chunks \u00b7 ' + d.total_count + ' total \u00b7 ' +
                 d.elapsed_ms + ' ms', 'upload-ok');
        } else {
          failCount++;
          let msg = '  \u2717 ' + f.name + ' failed: ' + (d.error || 'unknown');
          if (d.diagnostics) {
            const diag = d.diagnostics;
            msg += '\\n     blocks=' + (diag.blocks_returned || 0) +
                   ' rows=' + (diag.total_rows || 0) +
                   ' textchars=' + (diag.total_text_chars || 0);
            if (diag.hint) msg += '\\n     hint: ' + diag.hint;
          }
          addMsg(msg, 'upload-err');
        }
      } catch (e) {
        failCount++;
        addMsg('  \u2717 ' + f.name + ' error: ' + e.message, 'upload-err');
      }
    }

    if (total > 1) {
      addMsg('Done: ' + okCount + ' uploaded (' + totalChunks + ' chunks) \u00b7 ' + failCount + ' failed', 'upload-ok');
    }

    fileInput.value = '';
    refreshDocCount();
  });

  // Init
  try {
    const active = getActiveSession();
    if (active && active.messages && active.messages.length > 0) {
      loadSession(active.id);
    } else {
      createNewSession();
    }
  } catch (e) {
    // Fallback if anything goes wrong with storage
    renderSession();
    addMsg('Welcome to sunnyware. Ask me anything.', 'step', false);
  }
  renderSidebar();
  refreshDocCount();
  refreshProviders();
  input.focus();

  async function refreshProviders() {
    try {
      const r = await fetch('/api/providers/status');
      const d = await r.json();
      const el = document.getElementById('provBadge');
      if (!el) return;
      const provs = d.providers || [];
      if (provs.length === 0) {
        el.textContent = 'providers: none';
        return;
      }
      const live = provs.filter(p => !p.cooling).length;
      const firstLive = provs.find(p => !p.cooling);
      const label = firstLive ? firstLive.name : provs[0].name;
      el.textContent = 'providers: ' + live + '/' + provs.length + ' (' + label + ')';
    } catch (e) {
      const el = document.getElementById('provBadge');
      if (el) el.textContent = 'providers: ?';
    }
  }
})();
</script>
</body>
</html>
"""
