# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal self-contained web chat UI for sunnyware."""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>sunnyware</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
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
  #sidebar .hdr { display: flex; gap: 6px; align-items: center; }
  #newChatBtn { flex: 1; }
  .icon-btn { flex: 0 0 auto; width: 34px; height: 34px; padding: 0;
              background: #1d2026; color: #b8c4d0;
              border: 1px solid #2a2e36; border-radius: 6px;
              cursor: pointer; font-size: 14px; line-height: 1;
              display: flex; align-items: center; justify-content: center; }
  .icon-btn:hover { background: #252932; border-color: #52b788; color: #e6e8eb; }
  .icon-btn-wide { padding: 8px 12px; background: #1d2026; color: #b8c4d0;
                   border: 1px solid #2a2e36; border-radius: 6px;
                   cursor: pointer; font-size: 12px; font-family: inherit;
                   white-space: nowrap; }
  .icon-btn-wide:hover { background: #252932; border-color: #52b788;
                         color: #e6e8eb; }

  /* Part 40: usage dashboard modal */
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7);
                   display: flex; align-items: center; justify-content: center;
                   z-index: 1000; }
  .modal-panel { background: #121418; border: 1px solid #2a2e36;
                 border-radius: 10px; width: min(780px, 92vw);
                 max-height: 85vh; display: flex; flex-direction: column; }
  .modal-hdr { padding: 12px 18px; border-bottom: 1px solid #1d2026;
               display: flex; justify-content: space-between;
               align-items: center; font-weight: 600; color: #ffb454; }
  .modal-body { padding: 18px; overflow-y: auto; flex: 1; }
  .usage-grid { display: grid; grid-template-columns: repeat(4, 1fr);
                gap: 10px; margin-bottom: 18px; }
  .usage-card { background: #0e1014; border: 1px solid #1d2026;
                border-radius: 8px; padding: 12px; }
  .usage-card .k { font-size: 11px; color: #6e7480;
                   text-transform: uppercase; letter-spacing: 0.5px; }
  .usage-card .v { font-size: 20px; color: #e6e8eb; margin-top: 6px;
                   font-weight: 600; }
  .usage-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .usage-table th, .usage-table td { padding: 8px 10px; text-align: left;
                                     border-bottom: 1px solid #1d2026; }
  .usage-table th { color: #6e7480; font-weight: 600; font-size: 11px;
                    text-transform: uppercase; letter-spacing: 0.5px; }
  .usage-table td { color: #b8c4d0; }
  .usage-table td.num { text-align: right; font-family: monospace; }
  .usage-h { margin-top: 8px; margin-bottom: 10px; color: #ffb454;
             font-size: 14px; }
  .usage-loading { color: #6e7480; font-style: italic; padding: 20px;
                   text-align: center; }
  #importInput { display: none; }
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
  /* Part 42: markdown rendering for assistant messages */
  .msg.agent { white-space: normal; }
  .msg.agent p { margin: 0 0 10px 0; }
  .msg.agent p:last-child { margin-bottom: 0; }
  .msg.agent code { background: #1d2026; padding: 2px 5px; border-radius: 3px;
                    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; }
  .msg.agent pre { background: #0a0c0f; border: 1px solid #1d2026; border-radius: 6px;
                   padding: 10px 14px; overflow-x: auto; margin: 8px 0; }
  .msg.agent pre code { background: none; padding: 0; font-size: 12.5px; }
  .msg.agent h1, .msg.agent h2, .msg.agent h3 { color: #ffb454; margin: 12px 0 6px 0; }
  .msg.agent h1 { font-size: 18px; }
  .msg.agent h2 { font-size: 16px; }
  .msg.agent h3 { font-size: 14px; }
  .msg.agent ul, .msg.agent ol { margin: 6px 0 6px 22px; padding: 0; }
  .msg.agent li { margin: 2px 0; }
  .msg.agent a { color: #6e9bd8; }
  .msg.agent blockquote { border-left: 3px solid #2a2e36; padding-left: 12px;
                          color: #b8c4d0; margin: 8px 0; }
  .msg.agent table { border-collapse: collapse; margin: 8px 0; }
  .msg.agent th, .msg.agent td { border: 1px solid #2a2e36; padding: 5px 10px; }
  .msg.agent th { background: #1d2026; color: #ffb454; }
  .msg.agent hr { border: none; border-top: 1px solid #2a2e36; margin: 12px 0; }
  /* Part 43: chart rendering */
  .msg.agent img { max-width: 100%; border: 1px solid #2a2e36; border-radius: 6px;
                   margin: 8px 0; cursor: zoom-in; background: #fff; }
  .msg.agent img.zoomed { position: fixed; inset: 5vh 5vw; width: 90vw; height: 90vh;
                          object-fit: contain; z-index: 2000; cursor: zoom-out;
                          background: #0a0c0f; padding: 12px; border-radius: 10px; }
  /* Part 43: mic button */
  #micBtn { padding: 12px 14px; border-radius: 8px; border: 1px solid #2a2e36;
            background: #1d2026; color: #b8c4d0; cursor: pointer; font-size: 16px; }
  #micBtn:hover { background: #252932; border-color: #52b788; color: #e6e8eb; }
  #micBtn.recording { background: #3a1a1a; border-color: #ff6b6b; color: #ff6b6b;
                      animation: pulse-red 1.2s infinite; }
  @keyframes pulse-red { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
  /* Part 43: session rename */
  .sess .ren { opacity: 0; color: #6e7480; font-size: 12px; padding: 0 3px; cursor: pointer; }
  .sess:hover .ren { opacity: 1; }
  .sess .ren:hover { color: #ffb454; }
  /* ════ Part 44: responsive CSS ════ */
  #mobileMenuBtn {
    display: none; width: 40px; height: 40px; padding: 0;
    background: transparent; border: 1px solid #2a2e36;
    border-radius: 6px; color: #e6e8eb; cursor: pointer;
    align-items: center; justify-content: center; font-size: 20px;
    flex: 0 0 auto;
  }
  #mobileMenuBtn:hover { background: #252932; border-color: #52b788; }
  .overlay-backdrop {
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,0.55); z-index: 850; cursor: pointer;
  }
  body.mobile-menu-open .overlay-backdrop { display: block; }
  @media (max-width: 640px) {
    header { padding: 10px 14px; }
    header h1 { font-size: 15px; }
    header .meta { font-size: 11px; }
    header .meta a { margin-left: 8px; font-size: 11px; }
    #mobileMenuBtn { display: flex; }
    #sidebar {
      position: fixed; top: 0; left: 0; bottom: 0;
      width: 260px; min-width: 260px; z-index: 900;
      transform: translateX(-100%); transition: transform 0.25s ease;
      box-shadow: 4px 0 16px rgba(0,0,0,0.55);
    }
    body.mobile-menu-open #sidebar { transform: translateX(0); }
    #chat { padding: 14px; }
    .msg { font-size: 14px; }
    .footer-info { font-size: 10px; }
    form { gap: 6px; }
    input[type=text] { padding: 12px 14px; font-size: 15px; }
    #send { padding: 12px 18px; }
    #micBtn { padding: 12px 14px; }
  }
  @media (min-width: 641px) and (max-width: 900px) {
    #sidebar { width: 200px; min-width: 200px; }
    #chat { padding: 16px; }
    form { gap: 8px; }
  }
  @media (min-width: 1600px) {
    header { padding: 16px 32px; }
    header h1 { font-size: 20px; }
    #chat { max-width: 1100px; padding: 28px; }
    .msg { font-size: 16px; line-height: 1.6; }
    #sidebar { width: 300px; min-width: 300px; }
    input[type=text] { font-size: 16px; padding: 14px 18px; }
    #send, #micBtn { padding: 14px 22px; font-size: 15px; }
  }
  @media (pointer: coarse) {
    button, .icon-btn, .icon-btn-wide, .sess { min-height: 44px; }
    .sess { padding: 12px 16px; }
    .sess .del, .sess .ren { font-size: 16px; padding: 0 6px; }
  }
  body.tv-mode { font-size: 18px; }
  body.tv-mode header { padding: 20px 40px; }
  body.tv-mode header h1 { font-size: 24px; }
  body.tv-mode #chat { max-width: 1200px; padding: 32px; }
  body.tv-mode .msg { font-size: 18px; line-height: 1.7; }
  body.tv-mode #sidebar { width: 340px; min-width: 340px; }
  body.tv-mode .sess { padding: 16px 20px; font-size: 15px; }
  body.tv-mode button,
  body.tv-mode .icon-btn,
  body.tv-mode .icon-btn-wide { min-height: 56px; font-size: 16px; padding: 16px 24px; }
  body.tv-mode #input { font-size: 18px; padding: 18px 24px; }
  body.tv-mode button:focus,
  body.tv-mode input:focus,
  body.tv-mode .sess:focus,
  body.tv-mode a:focus { outline: 3px solid #52b788; outline-offset: 3px; }
  #micBtn.mic-denied { border-color: #ff6b6b; color: #ff6b6b; opacity: 0.75; }
</style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;gap:10px;">
    <button id="mobileMenuBtn" type="button" title="Menu">&#9776;</button>
    <h1>sunnyware</h1>
  </div>
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
<div id="usageModal" class="modal-overlay" style="display:none">
  <div class="modal-panel">
    <div class="modal-hdr">
      <span>Token Usage Dashboard</span>
      <button id="usageClose" class="icon-btn" type="button" title="Close">\u00d7</button>
    </div>
    <div class="modal-body" id="usageBody">
      <div class="usage-loading">Loading usage data...</div>
    </div>
  </div>
</div>
<div class="overlay-backdrop" id="overlayBackdrop"></div>
<div id="layout">
  <aside id="sidebar">
    <div class="hdr">
      <button id="newChatBtn" type="button">+ New chat</button>
      <button id="exportBtn" class="icon-btn" type="button" title="Export all sessions as JSON">\u2b07</button>
      <button id="importBtn" class="icon-btn" type="button" title="Import sessions from JSON">\u2b06</button>
      <button id="usageBtn" class="icon-btn-wide" type="button" title="Token usage dashboard">Stats</button>
    </div>
    <input type="file" id="importInput" accept=".json,application/json">
    <div id="sessionList"></div>
  </aside>
  <div id="main">
    <div id="chat"></div>
    <footer>
      <form id="form">
        <input type="text" id="input" placeholder="Ask anything..." autocomplete="off" required>
        <button type="button" id="micBtn" title="Voice input (click to start/stop)">\U0001F3A4</button>
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

  // Part 38: Neon fallback (fetch history from DB if localStorage lost it)
  async function fetchSessionsFromNeon() {
    try {
      const r = await fetch('/api/sessions');
      if (!r.ok) return [];
      const d = await r.json();
      return d.sessions || [];
    } catch (e) {
      return [];
    }
  }

  async function fetchHistoryFromNeon(sessionKey) {
    try {
      const r = await fetch('/api/sessions/' + encodeURIComponent(sessionKey) + '/history?limit=200');
      if (!r.ok) return [];
      const d = await r.json();
      const events = d.events || [];
      const messages = [];
      for (let i = 0; i < events.length; i++) {
        const e = events[i];
        let payload;
        try { payload = JSON.parse(e.payload || '{}'); } catch (err) { continue; }
        const content = (payload && payload.content) || '';
        if (!content) continue;
        const ts = Date.parse(e.created_at) || Date.now();
        if (e.event_type === 'user_message') {
          messages.push({ role: 'user', text: content, ts: ts });
        } else if (e.event_type === 'assistant_message') {
          messages.push({ role: 'agent', text: content, ts: ts });
        }
      }
      return messages;
    } catch (e) {
      return [];
    }
  }

  async function hydrateFromNeon() {
    const local = getSessions();
    const neonSessions = await fetchSessionsFromNeon();
    if (!neonSessions || neonSessions.length === 0) return 0;
    let merged = 0;
    for (let i = 0; i < neonSessions.length; i++) {
      const s = neonSessions[i];
      const key = s.session_key || '';
      if (!key.startsWith('web-')) continue;
      if (local[key]) continue;
      const msgs = await fetchHistoryFromNeon(key);
      if (!msgs || msgs.length === 0) continue;
      let title = 'New chat';
      for (let j = 0; j < msgs.length; j++) {
        if (msgs[j].role === 'user' && msgs[j].text) {
          title = msgs[j].text.length > 40 ? msgs[j].text.slice(0, 40) : msgs[j].text;
          break;
        }
      }
      local[key] = {
        id: key,
        title: title,
        created: Date.parse(s.created_at) || Date.now(),
        messages: msgs
      };
      merged++;
    }
    if (merged > 0) saveSessions(local);
    return merged;
  }

  async function loadSessionWithFallback(id) {
    if (!id) return;
    const local = getSessions();
    if (local[id]) {
      loadSession(id);
      return;
    }
    const msgs = await fetchHistoryFromNeon(id);
    if (!msgs || msgs.length === 0) return;
    let title = 'New chat';
    for (let i = 0; i < msgs.length; i++) {
      if (msgs[i].role === 'user' && msgs[i].text) {
        title = msgs[i].text.length > 40 ? msgs[i].text.slice(0, 40) : msgs[i].text;
        break;
      }
    }
    const local2 = getSessions();
    local2[id] = {
      id: id,
      title: title,
      created: Date.now(),
      messages: msgs
    };
    saveSessions(local2);
    loadSession(id);
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
      title.title = 'Double-click to rename';
      title.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        renameSession(s.id);
      });
      row.appendChild(title);

      const ren = document.createElement('span');
      ren.className = 'ren';
      ren.textContent = '\u270F';
      ren.title = 'Rename';
      ren.addEventListener('click', (ev) => {
        ev.stopPropagation();
        renameSession(s.id);
      });
      row.appendChild(ren);

      const del = document.createElement('span');
      del.className = 'del';
      del.textContent = '\u00d7';
      del.title = 'Delete';
      del.addEventListener('click', (ev) => {
        ev.stopPropagation();
        deleteSession(s.id);
      });
      row.appendChild(del);

      row.addEventListener('click', () => { loadSessionWithFallback(s.id); });
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

  function renameSession(id) {
    const sessions = getSessions();
    const sess = sessions[id];
    if (!sess) return;
    const current = sess.title || 'New chat';
    const next = window.prompt('Rename session:', current);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed) return;
    sess.title = trimmed.length > 60 ? trimmed.slice(0, 60) + '...' : trimmed;
    saveSessions(sessions);
    renderSidebar();
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

  // Part 42: markdown rendering for assistant messages
  function escapeHtml(s) {
    var esc = {};
    esc[38] = '&amp;';
    esc[60] = '&lt;';
    esc[62] = '&gt;';
    esc[34] = '&quot;';
    esc[39] = '&#39;';
    var out = '';
    s = String(s);
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      out += esc[ch.charCodeAt(0)] || ch;
    }
    return out;
  }
  function wrapBareBase64(t) {
    var magic = 'iVBORw0KGgo';
    var out = '';
    var cursor = 0;
    while (true) {
      var idx = t.indexOf(magic, cursor);
      if (idx === -1) { out += t.slice(cursor); break; }
      var lookback = t.slice(Math.max(0, idx - 40), idx);
      if (lookback.indexOf('data:image') !== -1) {
        out += t.slice(cursor, idx + magic.length);
        cursor = idx + magic.length;
        continue;
      }
      var end = idx;
      while (end < t.length) {
        var ch = t.charAt(end);
        var isB64 = (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                    (ch >= '0' && ch <= '9') ||
                    ch === '+' || ch === '/' || ch === '=';
        if (!isB64) break;
        end++;
      }
      var blob = t.slice(idx, end);
      if (blob.length < 500) {
        out += t.slice(cursor, end);
        cursor = end;
        continue;
      }
      out += t.slice(cursor, idx);
      out += '![chart](data:image/png;base64,' + blob + ')';
      cursor = end;
    }
    return out;
  }

  function renderAgentHtml(text) {
    if (!text) return '';
    if (typeof marked === 'undefined' || !marked.parse) return escapeHtml(text);
    try {
      var raw = marked.parse(wrapBareBase64(text));
      raw = raw.split('<\/script').join('&lt;/script');
      raw = raw.split('javascript:').join('');
      return raw;
    } catch (e) {
      return escapeHtml(text);
    }
  }

  function addMsg(text, cls, persist) {
    if (persist === undefined) persist = true;
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    if (cls === 'agent') {
      d.innerHTML = renderAgentHtml(text);
    } else {
      d.textContent = text;
    }
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
                ensureBubble().innerHTML = renderAgentHtml(agentText);
                chat.scrollTop = chat.scrollHeight;
              }
            } else if (type === 'answer') {
              const ans = data.text || '';
              if (ans) {
                agentText = ans;
                ensureBubble().innerHTML = renderAgentHtml(agentText);
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

  // Part 39: export/import sessions
  function exportSessions() {
    try {
      const sessions = getSessions();
      const payload = {
        version: 1,
        exported_at: new Date().toISOString(),
        source: 'sunnyware-webui',
        session_count: Object.keys(sessions).length,
        sessions: sessions
      };
      const json = JSON.stringify(payload, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.href = url;
      a.download = 'sunnyware-sessions-' + ts + '.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addMsg('Exported ' + payload.session_count + ' session(s) to JSON.', 'upload-ok', false);
    } catch (e) {
      addMsg('Export failed: ' + e.message, 'upload-err', false);
    }
  }

  async function importSessions(file) {
    if (!file) return;
    try {
      const text = await file.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        addMsg('Import failed: invalid JSON file', 'upload-err', false);
        return;
      }
      // Accept two shapes: {sessions: {...}} (our export) or flat {...}
      let incoming = {};
      if (data && typeof data === 'object' && data.sessions && typeof data.sessions === 'object') {
        incoming = data.sessions;
      } else if (data && typeof data === 'object') {
        incoming = data;
      } else {
        addMsg('Import failed: unexpected JSON shape', 'upload-err', false);
        return;
      }
      const local = getSessions();
      let added = 0;
      let merged = 0;
      for (const id of Object.keys(incoming)) {
        const s = incoming[id];
        if (!s || !s.id || !Array.isArray(s.messages)) continue;
        if (!local[id]) {
          local[id] = s;
          added++;
        } else {
          // Merge: keep union of messages by ts
          const seen = new Set((local[id].messages || []).map(m => m.ts + '|' + (m.text || '').slice(0, 30)));
          let newMsgs = 0;
          for (const m of s.messages) {
            const key = m.ts + '|' + (m.text || '').slice(0, 30);
            if (!seen.has(key)) {
              local[id].messages.push(m);
              seen.add(key);
              newMsgs++;
            }
          }
          if (newMsgs > 0) merged++;
        }
      }
      saveSessions(local);
      renderSidebar();
      addMsg('Import complete: ' + added + ' new session(s), ' + merged + ' merged.', 'upload-ok', false);
    } catch (e) {
      addMsg('Import failed: ' + e.message, 'upload-err', false);
    } finally {
      const inp = document.getElementById('importInput');
      if (inp) inp.value = '';
    }
  }

  // Part 40: token usage dashboard
  async function openUsageModal() {
    const modal = document.getElementById('usageModal');
    if (!modal) return;
    modal.style.display = 'flex';
    const body = document.getElementById('usageBody');
    body.innerHTML = '';
    const loading = document.createElement('div');
    loading.className = 'usage-loading';
    loading.textContent = 'Loading usage data...';
    body.appendChild(loading);
    try {
      const results = await Promise.all([
        fetch('/api/usage'),
        fetch('/api/usage/pricing'),
      ]);
      const usage = await results[0].json();
      const pricing = await results[1].json();
      renderUsageDashboard(usage, pricing);
    } catch (err) {
      body.innerHTML = '';
      const errDiv = document.createElement('div');
      errDiv.className = 'usage-loading';
      errDiv.textContent = 'Failed to load: ' + err.message;
      body.appendChild(errDiv);
    }
  }

  function closeUsageModal() {
    const modal = document.getElementById('usageModal');
    if (modal) modal.style.display = 'none';
  }

  function fmtNum(n) {
    n = Number(n) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
  }

  function addUsageCard(parent, key, value) {
    const card = document.createElement('div');
    card.className = 'usage-card';
    const k = document.createElement('div');
    k.className = 'k';
    k.textContent = key;
    card.appendChild(k);
    const v = document.createElement('div');
    v.className = 'v';
    v.textContent = String(value);
    card.appendChild(v);
    parent.appendChild(card);
  }

  function addTableCell(row, text, isNum) {
    const td = document.createElement('td');
    if (isNum) td.className = 'num';
    td.textContent = String(text);
    row.appendChild(td);
  }

  function renderUsageDashboard(usage, pricing) {
    const body = document.getElementById('usageBody');
    if (!body) return;
    body.innerHTML = '';
    const persisted = usage.persisted || {};
    const byModel = usage.by_model || [];
    const grid = document.createElement('div');
    grid.className = 'usage-grid';
    addUsageCard(grid, 'Total calls', fmtNum(persisted.calls));
    addUsageCard(grid, 'Input tokens', fmtNum(persisted.input_tokens));
    addUsageCard(grid, 'Output tokens', fmtNum(persisted.output_tokens));
    addUsageCard(grid, 'Cost (USD)', '$' + (Number(persisted.cost_usd) || 0).toFixed(4));
    body.appendChild(grid);
    const info = document.createElement('div');
    info.style.cssText = 'color:#6e7480; font-size:12px; margin-bottom:14px;';
    info.textContent = 'Window: last ' + (usage.window_days || 7) + ' days';
    body.appendChild(info);
    const h1 = document.createElement('div');
    h1.className = 'usage-h';
    h1.textContent = 'By model';
    body.appendChild(h1);
    const t1 = document.createElement('table');
    t1.className = 'usage-table';
    const thead1 = document.createElement('thead');
    const tr1 = document.createElement('tr');
    const cols1 = ['Model', 'Calls', 'Input', 'Output', 'Cost'];
    for (let i = 0; i < cols1.length; i++) {
      const th = document.createElement('th');
      th.textContent = cols1[i];
      tr1.appendChild(th);
    }
    thead1.appendChild(tr1);
    t1.appendChild(thead1);
    const tb1 = document.createElement('tbody');
    if (byModel.length === 0) {
      const row = document.createElement('tr');
      addTableCell(row, 'No data yet');
      tb1.appendChild(row);
    } else {
      for (let i = 0; i < byModel.length; i++) {
        const m = byModel[i];
        const row = document.createElement('tr');
        addTableCell(row, m.model || '?');
        addTableCell(row, fmtNum(m.calls), true);
        addTableCell(row, fmtNum(m.input_tokens), true);
        addTableCell(row, fmtNum(m.output_tokens), true);
        addTableCell(row, '$' + (Number(m.cost_usd) || 0).toFixed(4), true);
        tb1.appendChild(row);
      }
    }
    t1.appendChild(tb1);
    body.appendChild(t1);
    const h2 = document.createElement('div');
    h2.className = 'usage-h';
    h2.style.marginTop = '20px';
    h2.textContent = 'Pricing (USD per 1M tokens)';
    body.appendChild(h2);
    const t2 = document.createElement('table');
    t2.className = 'usage-table';
    const thead2 = document.createElement('thead');
    const tr2 = document.createElement('tr');
    const cols2 = ['Model', 'Input / 1M', 'Output / 1M'];
    for (let i = 0; i < cols2.length; i++) {
      const th = document.createElement('th');
      th.textContent = cols2[i];
      tr2.appendChild(th);
    }
    thead2.appendChild(tr2);
    t2.appendChild(thead2);
    const tb2 = document.createElement('tbody');
    const costTable = pricing.cost_table || [];
    for (let i = 0; i < costTable.length; i++) {
      const item = costTable[i];
      const row = document.createElement('tr');
      addTableCell(row, item.model || '?');
      addTableCell(row, '$' + (Number(item.input_per_million_usd) || 0).toFixed(2), true);
      addTableCell(row, '$' + (Number(item.output_per_million_usd) || 0).toFixed(2), true);
      tb2.appendChild(row);
    }
    t2.appendChild(tb2);
    body.appendChild(t2);
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

  // Part 39: export/import buttons
  const exportBtn = document.getElementById('exportBtn');
  const importBtn = document.getElementById('importBtn');
  const importInput = document.getElementById('importInput');
  if (exportBtn) {
    exportBtn.addEventListener('click', (e) => {
      e.preventDefault();
      exportSessions();
    });
  }
  if (importBtn && importInput) {
    importBtn.addEventListener('click', (e) => {
      e.preventDefault();
      importInput.click();
    });
    importInput.addEventListener('change', async () => {
      const f = importInput.files && importInput.files[0];
      if (f) await importSessions(f);
    });
  }

  // Part 40: usage dashboard wiring
  const usageBtn = document.getElementById('usageBtn');
  const usageClose = document.getElementById('usageClose');
  const usageModal = document.getElementById('usageModal');
  if (usageBtn) {
    usageBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openUsageModal();
    });
  }
  if (usageClose) {
    usageClose.addEventListener('click', (e) => {
      e.preventDefault();
      closeUsageModal();
    });
  }
  if (usageModal) {
    usageModal.addEventListener('click', (e) => {
      if (e.target === usageModal) closeUsageModal();
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
      renderSidebar();
    } else {
      // Part 38: localStorage empty -> try Neon hydration first
      hydrateFromNeon().then((merged) => {
        const active2 = getActiveSession();
        if (active2 && active2.messages && active2.messages.length > 0) {
          loadSession(active2.id);
        } else {
          createNewSession();
        }
        renderSidebar();
        if (merged > 0) {
          const note = document.createElement('div');
          note.className = 'msg step';
          note.textContent = 'Restored ' + merged + ' session(s) from database.';
          chat.insertBefore(note, chat.firstChild);
        }
      }).catch(() => {
        createNewSession();
        renderSidebar();
      });
    }
  } catch (e) {
    renderSession();
    addMsg('Welcome to sunnyware. Ask me anything.', 'step', false);
    renderSidebar();
  }
  refreshDocCount();
  input.focus();

  // Part 43: chart click-to-zoom
  chat.addEventListener('click', (e) => {
    if (e.target.tagName === 'IMG' && e.target.closest('.msg.agent')) {
      e.target.classList.toggle('zoomed');
    } else if (e.target.classList && e.target.classList.contains('zoomed')) {
      e.target.classList.remove('zoomed');
    }
  });

  // Part 43: voice input via Web Speech API
  (function initVoice() {
    const btn = document.getElementById('micBtn');
    if (!btn) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      btn.title = 'Voice input not supported in this browser';
      btn.disabled = true;
      btn.style.opacity = '0.4';
      return;
    }
    let rec = null;
    let active = false;
    function startRecognition() {
      rec = new SR();
      rec.lang = navigator.language || navigator.userLanguage || 'en-US';
      rec.interimResults = true;
      rec.continuous = false;
      var base = input.value ? input.value + ' ' : '';
      rec.onstart = function () {
        active = true;
        btn.classList.add('recording');
        btn.title = 'Listening... click to stop';
      };
      rec.onresult = function (ev) {
        var interim = '', final = '';
        for (var i = ev.resultIndex; i < ev.results.length; i++) {
          var r = ev.results[i];
          if (r.isFinal) final += r[0].transcript;
          else interim += r[0].transcript;
        }
        input.value = base + final + interim;
      };
      rec.onerror = function (ev) {
        addMsg('voice error: ' + (ev.error || 'unknown'), 'error', false);
      };
      rec.onend = function () {
        active = false;
        btn.classList.remove('recording');
        btn.title = 'Voice input (click to start/stop)';
        input.focus();
      };
      rec.start();
    }

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      if (active && rec) { rec.stop(); return; }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        addMsg('voice: getUserMedia not available in this browser', 'error', false);
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
          stream.getTracks().forEach(function (t) { t.stop(); });
          startRecognition();
        })
        .catch(function (err) {
          var name = (err && err.name) ? err.name : '';
          var msg;
          if (name === 'NotAllowedError' || name === 'SecurityError') {
            msg = 'mic blocked - click padlock in URL bar then Microphone then Allow';
          } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
            msg = 'no microphone found on this device';
          } else {
            msg = 'mic error: ' + (err && err.message ? err.message : String(err));
          }
          addMsg('voice: ' + msg, 'error', false);
        });
    });
  })();

  // Part 44: TV user-agent detection
  (function detectTVMode() {
    var ua = navigator.userAgent || '';
    var signs = ['SmartTV', 'Tizen', 'Web0S', 'WebOS', 'NetCast', 'HbbTV',
                 'Viera', 'BRAVIA', 'AquosBrowser', 'SMART-TV', 'AppleTV',
                 'CrKey', 'FireTV', 'AFT'];
    for (var i = 0; i < signs.length; i++) {
      if (ua.indexOf(signs[i]) !== -1) {
        document.body.classList.add('tv-mode');
        return;
      }
    }
  })();

  // Part 44: mic permission state UI
  (function initMicPermissionUI() {
    var btn = document.getElementById('micBtn');
    if (!btn || !navigator.permissions || !navigator.permissions.query) return;
    function setState(state) {
      if (state === 'granted') {
        btn.title = 'Voice input (click to start/stop)';
        btn.classList.remove('mic-denied');
      } else if (state === 'denied') {
        btn.title = 'Mic blocked - click padlock in URL bar to allow';
        btn.classList.add('mic-denied');
      } else {
        btn.title = 'Voice input (browser will ask for permission)';
        btn.classList.remove('mic-denied');
      }
    }
    try {
      navigator.permissions.query({ name: 'microphone' }).then(function (r) {
        setState(r.state);
        r.onchange = function () { setState(r.state); };
      }).catch(function () { /* Firefox may not expose mic query */ });
    } catch (e) { /* ignore */ }
  })();

  // Part 44: mobile drawer menu
  (function initMobileMenu() {
    var btn = document.getElementById('mobileMenuBtn');
    var backdrop = document.getElementById('overlayBackdrop');
    function close() { document.body.classList.remove('mobile-menu-open'); }
    function toggle() { document.body.classList.toggle('mobile-menu-open'); }
    if (btn) btn.addEventListener('click', function (e) { e.preventDefault(); toggle(); });
    if (backdrop) backdrop.addEventListener('click', close);
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.closest && t.closest('.sess')) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });
  })();

})();
</script>
</body>
</html>
"""
