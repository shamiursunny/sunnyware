# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Minimal self-contained web chat UI for sunnyware."""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0e1014">
<title>sunnyware</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="/static/marked.min.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" defer></script>
<style>
  :root {
    --fs-xs: 11px;
    --fs-sm: 12.5px;
    --fs-base: 14px;
    --fs-lg: 15px;
    --fs-xl: 18px;
    --sp-1: 4px;
    --sp-2: 8px;
    --sp-3: 12px;
    --sp-4: 16px;
    --sp-5: 24px;
    --r-sm: 4px;
    --r-md: 6px;
    --r-lg: 8px;
    --r-xl: 10px;
    --r-full: 999px;
    --touch: 32px;
    --header-h: 44px;
    --sidebar-w: 248px;
    --chat-max: min(760px, 100%);
    --composer-max: min(760px, 100%);
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
    --dur: 0.12s;

    /* ═══ Part 70: neutral, structure-first palette ═══
       Pure grayscale (0% saturation) — no hue tint. Structure comes from
       1px borders, not from glows. Accent is used ONLY on primary CTA. */

    --bg:          #0c0c0d;
    --bg-elev:     #111113;
    --bg-sidebar:  #0a0a0b;
    --bg-hover:    #18181b;
    --bg-active:   #202023;
    --bg-input:    #111113;

    --border:      rgba(255,255,255,0.07);
    --border-2:    rgba(255,255,255,0.10);
    --border-3:    rgba(255,255,255,0.14);
    --border-strong: rgba(255,255,255,0.20);

    --text:        #ededef;
    --text-dim:    #a1a1a6;
    --text-mute:   #6e6e76;
    --text-faint:  #48484f;

    /* Single accent — used only on primary CTA */
    --accent:      #4ade80;
    --accent-hover:#5eea8e;
    --accent-ink:  #052e16;

    --danger:      #f87171;
    --link:        #93b8e8;

    --shadow-sm: 0 1px 2px rgba(0,0,0,0.5);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.5);
    --shadow-lg: 0 12px 32px rgba(0,0,0,0.6);

    --glass-bg: rgba(17,17,19,0.85);
    --glass-blur: blur(16px) saturate(1.2);
}
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: var(--fs-base); line-height: 1.55;
    color: var(--text); background: var(--bg);
    height: 100vh; height: 100dvh;
    display: flex; flex-direction: column; overflow: hidden;
    -webkit-tap-highlight-color: transparent;
    -webkit-font-smoothing: antialiased;
  }
  header {
    display: flex; align-items: center;
    height: var(--header-h); padding: 0 var(--sp-3);
    background: var(--bg-elev); border-bottom: 1px solid var(--border);
    flex-shrink: 0; z-index: 100; gap: var(--sp-2);
  }
  .header-left { display: flex; align-items: center; gap: var(--sp-2); flex: 1; min-width: 0; }
  header h1 { font-size: var(--fs-lg); font-weight: 700; color: var(--accent-2); white-space: nowrap; }
  .header-right { display: flex; align-items: center; gap: var(--sp-1); flex-shrink: 0; }

  /* Part 112: role persona selector */
  #roleSelect {
    background: rgba(255,255,255,.06);
    color: inherit;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 6px;
    padding: 4px 26px 4px 10px;
    font-size: var(--fs-xs);
    font-family: inherit;
    cursor: pointer;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='%23888' d='M0 0l5 6 5-6z'/></svg>");
    background-repeat: no-repeat;
    background-position: right 8px center;
    max-width: 160px;
    transition: border-color .15s ease, background-color .15s ease;
  }
  #roleSelect:hover { border-color: rgba(255,255,255,.3); }
  #roleSelect:focus { border-color: var(--accent, #5ba3ff); }
  #roleSelect option { background: #1a1a1a; color: #e6e6e6; }
  @media (max-width: 720px) {
    #roleSelect { max-width: 90px; padding-right: 22px; }
  }
  .header-meta-desktop { display: flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-xs); color: var(--text-mute); margin-right: var(--sp-2); }
  .header-meta-desktop > * { white-space: nowrap; }
  .header-meta-desktop a { color: var(--link); text-decoration: none; font-size: var(--fs-xs); }
  .header-meta-desktop a:hover { color: var(--accent); }
  .badge { display: inline-block; background: var(--bg-hover); color: var(--text-dim); padding: 2px 8px; border-radius: var(--r-full); font-size: var(--fs-xs); }
  .btn-icon {
    display: flex; align-items: center; justify-content: center;
    width: var(--touch); height: var(--touch); min-width: var(--touch);
    background: transparent; border: 1px solid var(--border-2);
    border-radius: var(--r-md); color: var(--text-dim);
    font-size: 20px; cursor: pointer;
    transition: all var(--dur) var(--ease);
    user-select: none;
  }
  .btn-icon:hover { background: var(--bg-hover); border-color: var(--accent); color: var(--text); }
  .btn-icon:active { transform: scale(0.94); }
  #mobileMenuBtn { display: none; }
  #mobileMenuBtn.show { display: flex; }
  /* Part 94: overflow menu button always visible (ChatGPT-style) */
  .overflow-panel {
    display: none; position: fixed;
    top: calc(var(--header-h) + 4px); right: var(--sp-2);
    background: var(--glass-bg);
    -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur);
    border: 1px solid var(--border-2); border-radius: var(--r-lg);
    padding: var(--sp-3); min-width: 220px;
    box-shadow: var(--shadow-lg); z-index: 1100;
    flex-direction: column; gap: var(--sp-2);
  }
  .overflow-panel.open { display: flex; }
  .overflow-panel a, .overflow-panel button {
    display: flex; align-items: center; padding: var(--sp-2) var(--sp-3);
    color: var(--text-dim); text-decoration: none; font-size: var(--fs-sm);
    border-radius: var(--r-md); background: transparent; border: none;
    cursor: pointer; width: 100%; text-align: left; font-family: inherit;
  }
  .overflow-panel a:hover, .overflow-panel button:hover { background: var(--bg-hover); color: var(--text); }
  #layout { display: flex; flex: 1; overflow: hidden; min-height: 0; }
  #sidebar {
    width: var(--sidebar-w); min-width: var(--sidebar-w);
    background: var(--bg-sidebar); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
    transition: transform var(--dur) var(--ease), width var(--dur) var(--ease);
  }
  #sidebar .sidebar-hdr { padding: var(--sp-2); display: flex; gap: var(--sp-1); border-bottom: 1px solid var(--border); align-items: center; }
  #newChatBtn {
    flex: 1; display: flex; align-items: center; gap: var(--sp-2);
    padding: var(--sp-2) var(--sp-3); min-height: var(--touch);
    background: var(--bg-hover); color: var(--text);
    border: 1px solid var(--border-2); border-radius: var(--r-md);
    font-size: var(--fs-sm); font-family: inherit; cursor: pointer;
    transition: all var(--dur) var(--ease);
  }
  #newChatBtn:hover { background: var(--bg-active); border-color: var(--accent); }
  .icon-btn-wide {
    min-height: var(--touch); padding: 0 var(--sp-2);
    background: var(--bg-hover); color: var(--text-dim);
    border: 1px solid var(--border-2); border-radius: var(--r-md);
    cursor: pointer; font-size: var(--fs-sm); font-family: inherit; white-space: nowrap;
  }
  .icon-btn-wide:hover { background: var(--bg-active); border-color: var(--accent); color: var(--text); }
  #sessionList { flex: 1; overflow-y: auto; padding: var(--sp-1) 0; }
  #sessionList::-webkit-scrollbar { width: 4px; }
  #sessionList::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 2px; }
  .sess {
    display: flex; align-items: center; gap: var(--sp-2);
    padding: var(--sp-2) var(--sp-3); cursor: pointer;
    font-size: var(--fs-sm); color: var(--text-dim);
    border-left: 3px solid transparent; min-height: var(--touch);
  }
  .sess:hover { background: var(--bg-hover); }
  .sess.active { background: var(--bg-active); border-left-color: var(--accent); color: var(--text); }
  .sess .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sess .del, .sess .ren { opacity: 0; color: var(--text-mute); font-size: 14px; padding: 0 3px; cursor: pointer; }
  .sess:hover .del, .sess:hover .ren { opacity: 0.7; }
  .sess .del:hover { color: var(--danger); }
  .sess .ren:hover { color: var(--accent-2); }
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; min-height: 0; }
  #chat { flex: 1; overflow-y: auto; overflow-x: hidden; padding: var(--sp-4); width: 100%; max-width: var(--chat-max); margin: 0 auto; }
  #chat::-webkit-scrollbar { width: 6px; }
  #chat::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
  .msg { margin-bottom: var(--sp-3); line-height: 1.6; white-space: pre-wrap; word-break: break-word; animation: msgIn 0.28s var(--ease); }
  @keyframes msgIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  .msg.user { color: var(--text-dim); padding: var(--sp-2) var(--sp-3); background: var(--bg-elev); border-radius: var(--r-lg) var(--r-lg) var(--r-sm) var(--r-lg); max-width: 88%; margin-left: auto; }
  .msg.agent { color: var(--text); padding-left: var(--sp-3); border-left: 3px solid var(--accent); background: transparent; white-space: normal; }
  .msg.error { color: var(--danger); }
  .msg.agent.budget { background: rgba(255, 176, 32, 0.08); border-left: 3px solid #ffb020; padding: var(--sp-2) var(--sp-3); border-radius: var(--r-md); }
  .msg.agent.budget::before { content: 'BUDGET LIMIT: '; display: block; color: #ffb020; font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.08em; margin-bottom: var(--sp-1); }

  /* Part 113B: per-role visual identity on agent bubbles */
  #chat[data-role="fpa"] .msg.agent     { border-left-color: #4a90e2; }
  #chat[data-role="quant"] .msg.agent   { border-left-color: #a855f7; }
  #chat[data-role="actuary"] .msg.agent { border-left-color: #10b981; }
  #chat[data-role="tax"] .msg.agent     { border-left-color: #f59e0b; }
  #chat[data-role="cfo"] .msg.agent     { border-left-color: #8b5cf6; }
  #chat[data-role="cdo"] .msg.agent     { border-left-color: #06b6d4; }

  #chat[data-role="fpa"] .msg.agent::before,
  #chat[data-role="quant"] .msg.agent::before,
  #chat[data-role="actuary"] .msg.agent::before,
  #chat[data-role="tax"] .msg.agent::before,
  #chat[data-role="cfo"] .msg.agent::before,
  #chat[data-role="cdo"] .msg.agent::before {
    display: block;
    font-size: var(--fs-xs);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 6px;
    opacity: 0.8;
  }
  #chat[data-role="fpa"] .msg.agent::before     { content: '📊 FP&A'; color: #4a90e2; }
  #chat[data-role="quant"] .msg.agent::before   { content: '🧮 QUANT'; color: #a855f7; }
  #chat[data-role="actuary"] .msg.agent::before { content: '🏦 ACTUARY'; color: #10b981; }
  #chat[data-role="tax"] .msg.agent::before     { content: '🧾 TAX'; color: #f59e0b; }
  #chat[data-role="cfo"] .msg.agent::before     { content: '💼 CFO'; color: #8b5cf6; }
  #chat[data-role="cdo"] .msg.agent::before     { content: '📋 CDO'; color: #06b6d4; }

  /* Part 115: role-specific content styling */
  /* FP&A: tables styled blue */
  #chat[data-role="fpa"] .msg.agent table         { border-color: #4a90e2; }
  #chat[data-role="fpa"] .msg.agent th            { background: rgba(74,144,226,0.12); color: #4a90e2; border-color: #4a90e2; }
  #chat[data-role="fpa"] .msg.agent h1,
  #chat[data-role="fpa"] .msg.agent h2            { color: #4a90e2; }

  /* Quant: code blocks styled purple */
  #chat[data-role="quant"] .msg.agent pre         { border-left: 3px solid #a855f7; background: rgba(168,85,247,0.04); }
  #chat[data-role="quant"] .msg.agent code        { color: #a855f7; }
  #chat[data-role="quant"] .msg.agent h1,
  #chat[data-role="quant"] .msg.agent h2          { color: #a855f7; }

  /* Actuary: tables + blockquotes styled emerald */
  #chat[data-role="actuary"] .msg.agent table     { border-color: #10b981; }
  #chat[data-role="actuary"] .msg.agent th        { background: rgba(16,185,129,0.12); color: #10b981; border-color: #10b981; }
  #chat[data-role="actuary"] .msg.agent blockquote{ border-left-color: #10b981; color: var(--text-dim); }
  #chat[data-role="actuary"] .msg.agent h1,
  #chat[data-role="actuary"] .msg.agent h2        { color: #10b981; }

  /* Tax: list markers styled amber */
  #chat[data-role="tax"] .msg.agent ol li::marker { color: #f59e0b; font-weight: 600; }
  #chat[data-role="tax"] .msg.agent ul li::marker { color: #f59e0b; }
  #chat[data-role="tax"] .msg.agent h1,
  #chat[data-role="tax"] .msg.agent h2            { color: #f59e0b; }

  /* CFO: deliverable document styling */
  #chat[data-role="cfo"] .msg.agent               { padding: var(--sp-3); background: rgba(139,92,246,0.04); border-radius: var(--r-md); }
  #chat[data-role="cfo"] .msg.agent h1,
  #chat[data-role="cfo"] .msg.agent h2            { color: #8b5cf6; }
  #chat[data-role="cfo"] .msg.agent table         { border-color: #8b5cf6; }
  #chat[data-role="cfo"] .msg.agent th            { background: rgba(139,92,246,0.12); color: #8b5cf6; border-color: #8b5cf6; }

  /* CDO: task-list style */
  #chat[data-role="cdo"] .msg.agent               { padding: var(--sp-2) var(--sp-3); background: rgba(6,182,212,0.04); border-radius: var(--r-md); }
  #chat[data-role="cdo"] .msg.agent h1,
  #chat[data-role="cdo"] .msg.agent h2            { color: #06b6d4; }
  .msg.step { font-size: var(--fs-xs); color: var(--text-mute); font-style: italic; padding: 2px 0; }
  .msg.upload { color: var(--accent-2); font-size: var(--fs-sm); }
  .msg.upload-ok { color: var(--accent); font-size: var(--fs-sm); }
  .msg.upload-err { color: var(--danger); font-size: var(--fs-sm); }
  .msg.agent p { margin: 0 0 var(--sp-2) 0; }
  .msg.agent p:last-child { margin-bottom: 0; }
  .msg.agent code { background: var(--bg-hover); padding: 2px 5px; border-radius: 4px; font-size: var(--fs-xs); font-family: ui-monospace, Menlo, Consolas, monospace; }
  .msg.agent pre { background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--sp-3); overflow-x: auto; margin: var(--sp-2) 0; }
  .msg.agent pre code { background: none; padding: 0; font-size: var(--fs-xs); }
  .msg.agent h1, .msg.agent h2, .msg.agent h3 { color: var(--accent-2); margin: var(--sp-3) 0 var(--sp-1) 0; line-height: 1.3; }
  .msg.agent h1 { font-size: var(--fs-xl); }
  .msg.agent h2 { font-size: var(--fs-lg); }
  .msg.agent h3 { font-size: var(--fs-base); }
  .msg-image { display: block; max-width: min(560px, 90%); border-radius: 12px; margin: 10px 0; box-shadow: 0 6px 20px rgba(0,0,0,0.35); animation: msgIn 0.28s var(--ease); }
  .msg.agent ul, .msg.agent ol { margin: var(--sp-1) 0 var(--sp-1) var(--sp-4); padding: 0; }
  .msg.agent li { margin: 2px 0; }
  .msg.agent a { color: var(--link); }
  .msg.agent blockquote { border-left: 3px solid var(--border-2); padding-left: var(--sp-3); color: var(--text-dim); margin: var(--sp-2) 0; }
  /* Part 166: markdown element polish */
  .msg.agent h1, .msg.agent h2, .msg.agent h3, .msg.agent h4 {
    margin: var(--sp-4) 0 var(--sp-2); line-height: 1.3; font-weight: 600;
    color: var(--text);
  }
  .msg.agent h1 { font-size: calc(var(--fs-lg) + 4px); }
  .msg.agent h2 { font-size: var(--fs-lg); border-bottom: 1px solid var(--border); padding-bottom: 4px; }
  .msg.agent h3 { font-size: var(--fs-md); }
  .msg.agent h4 { font-size: var(--fs-sm); text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); }
  .msg.agent h1:first-child, .msg.agent h2:first-child,
  .msg.agent h3:first-child, .msg.agent h4:first-child { margin-top: 0; }

  .msg.agent ul, .msg.agent ol { margin: var(--sp-2) 0; padding-left: 1.6em; }
  .msg.agent li { margin: 2px 0; line-height: 1.6; }
  .msg.agent li > p { margin: 0; }
  .msg.agent ul ul, .msg.agent ol ol,
  .msg.agent ul ol, .msg.agent ol ul { margin: 2px 0; }

  .msg.agent strong { font-weight: 600; color: var(--text); }
  .msg.agent em { font-style: italic; color: var(--text-dim); }

  .msg.agent a { color: var(--accent); text-decoration: underline;
    text-decoration-color: rgba(120, 160, 255, 0.35);
    text-underline-offset: 2px; transition: text-decoration-color .15s; }
  .msg.agent a:hover { text-decoration-color: var(--accent); }

  .msg.agent hr { border: 0; border-top: 1px solid var(--border); margin: var(--sp-3) 0; }

  .msg.agent table { width: 100%; border-collapse: collapse;
    margin: var(--sp-2) 0; font-size: var(--fs-xs); }
  .msg.agent th, .msg.agent td { border: 1px solid var(--border);
    padding: 6px 10px; text-align: left; vertical-align: top; }
  .msg.agent th { background: var(--bg-hover); font-weight: 600; }

  .msg.agent img { max-width: 100%; height: auto;
    border-radius: var(--r-md); margin: var(--sp-2) 0; }
  /* /Part 166 */
  .msg.agent table { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; margin: var(--sp-2) 0; }
  .msg.agent th, .msg.agent td { border: 1px solid var(--border-2); padding: 5px 10px; font-size: var(--fs-sm); }
  .msg.agent th { background: var(--bg-hover); color: var(--accent-2); }
  .msg.agent hr { border: none; border-top: 1px solid var(--border-2); margin: var(--sp-3) 0; }
  .msg.agent img { max-width: 100%; border: 1px solid var(--border); border-radius: var(--r-md); margin: var(--sp-2) 0; cursor: zoom-in; }
  .sunnyware-plotly { min-height: 320px; max-width: 100%; margin: 8px 0; }
  .msg.agent img.zoomed { position: fixed; inset: 4vh 4vw; width: 92vw; height: 92vh; object-fit: contain; z-index: 2000; cursor: zoom-out; background: var(--bg); padding: var(--sp-3); border-radius: var(--r-lg); }
  footer { padding: var(--sp-2) var(--sp-3) var(--sp-3); border-top: 1px solid var(--border); background: var(--bg-elev); flex-shrink: 0; }
  #form { max-width: var(--composer-max); margin: 0 auto; display: flex; gap: var(--sp-1); align-items: center; }
  #input { flex: 1; padding: 12px var(--sp-3); min-height: var(--touch); border-radius: var(--r-xl); border: 1px solid var(--border-2); background: var(--bg-input); color: var(--text); font-size: var(--fs-base); font-family: inherit; outline: none; transition: border-color var(--dur) var(--ease); }
  #input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(82, 183, 136, 0.15); }
  #send { padding: 12px var(--sp-4); min-height: var(--touch); border-radius: var(--r-xl); border: none; background: var(--accent); color: var(--bg); font-weight: 600; font-size: var(--fs-sm); font-family: inherit; cursor: pointer; transition: all var(--dur) var(--ease); white-space: nowrap; }
  #send:hover { background: var(--accent-hover); }
  #send:active { transform: scale(0.97); }
  #send:disabled { opacity: 0.5; cursor: not-allowed; }
  #micBtn { padding: 12px; min-height: var(--touch); min-width: var(--touch); border-radius: var(--r-xl); border: 1px solid var(--border-2); background: var(--bg-input); color: var(--text-dim); cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }
  #micBtn:hover { border-color: var(--accent); color: var(--text); }
  #micBtn.recording { background: hsl(0 40% 18%); border-color: var(--danger); color: var(--danger); animation: pulse-red 1.2s infinite; }
  @keyframes pulse-red { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
  .footer-info { max-width: var(--composer-max); margin: var(--sp-1) auto 0; text-align: center; font-size: var(--fs-xs); color: var(--text-mute); }
  #fileInput, #importInput { display: none; }
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center; z-index: 1500; }
  .modal-panel { background: var(--bg-elev); border: 1px solid var(--border-2); border-radius: var(--r-lg); width: min(780px, 92vw); max-height: 85vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
  .modal-hdr { padding: var(--sp-3) var(--sp-4); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: var(--accent-2); font-size: var(--fs-lg); }
  .modal-body { padding: var(--sp-4); overflow-y: auto; flex: 1; }
  .usage-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--sp-2); margin-bottom: var(--sp-4); }
  .usage-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--sp-3); }
  .usage-card .k { font-size: var(--fs-xs); color: var(--text-mute); text-transform: uppercase; }
  .usage-card .v { font-size: var(--fs-xl); color: var(--text); margin-top: var(--sp-1); font-weight: 600; }
  .usage-table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  .usage-table th, .usage-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
  .usage-table th { color: var(--text-mute); font-weight: 600; font-size: var(--fs-xs); }
  .usage-table td { color: var(--text-dim); }
  .usage-table td.num { text-align: right; font-family: ui-monospace, monospace; }
  .usage-h { margin: var(--sp-2) 0; color: var(--accent-2); font-size: var(--fs-lg); }
  .usage-loading { color: var(--text-mute); font-style: italic; padding: var(--sp-4); text-align: center; }
  .overlay-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px); z-index: 850; opacity: 0; pointer-events: none; transition: opacity var(--dur) var(--ease); }
  body.mobile-menu-open .overlay-backdrop { opacity: 1; pointer-events: auto; }
  @media (max-width: 640px) {
    :root { --header-h: 48px; --touch: 44px; }
    #mobileMenuBtn, #overflowMenuBtn { display: flex; }
    .header-meta-desktop { display: none; }
    #sidebar { position: fixed; top: 0; left: 0; bottom: 0; width: min(280px, 82vw); min-width: min(280px, 82vw); z-index: 900; transform: translateX(-100%); background: var(--glass-bg); -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); box-shadow: var(--shadow-lg); border-right: 1px solid rgba(255,255,255,0.06); }
    body.mobile-menu-open #sidebar { transform: translateX(0); }
    #chat { padding: var(--sp-3) var(--sp-2); max-width: 100%; }
    .msg.user { max-width: 94%; }
    footer { padding: var(--sp-2); }
    .usage-grid { grid-template-columns: 1fr 1fr; }
    .modal-overlay { padding: 0; }
    .modal-panel { width: 100vw; max-width: 100vw; height: 100dvh; max-height: 100dvh; border-radius: 0; }
    #input { font-size: 16px; }
  }
  @media (min-width: 641px) and (max-width: 900px) {
    :root { --sidebar-w: 220px; }
    #overflowMenuBtn { display: flex; }
    .header-meta-desktop { display: none; }
  }
  @media (min-width: 901px) {
    #mobileMenuBtn { display: none !important; }
  }
  @media (min-width: 1400px) {
    :root { --sidebar-w: 300px; --chat-max: min(960px, 90vw); --composer-max: min(960px, 92vw); }
  }
  @media (pointer: coarse) {
    :root { --touch: 48px; }
    .sess { padding: var(--sp-3); }
  }
  body.device-tv { --touch: 56px; --header-h: 72px; --fs-base: 18px; --fs-lg: 22px; --chat-max: min(1400px, 92vw); }
  body.device-tv header { padding: 0 var(--sp-5); }
  body.device-tv #chat { padding: var(--sp-5); }
  body.device-tv .msg { font-size: 18px; line-height: 1.7; }
  body.device-tv button:focus, body.device-tv input:focus, body.device-tv .sess:focus, body.device-tv a:focus { outline: 3px solid var(--accent); outline-offset: 3px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
  }
  @media print {
    header, #sidebar, footer, .btn-icon, .overlay-backdrop { display: none !important; }
    #layout, #main, #chat { overflow: visible !important; height: auto !important; }
    body { background: #fff; color: #000; height: auto; }
    .msg { page-break-inside: avoid; }
  }
/* ═══ Part 68: professional typography + icon polish ═══ */
:root {
  --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --r-md: 10px;
  --r-lg: 12px;
  --r-xl: 24px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.25);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-lg: 0 12px 32px rgba(0,0,0,0.45);
  --accent: hsl(155 65% 52%);
  --accent-hover: hsl(155 65% 58%);
}
body, input, button, textarea {
  font-family: var(--font-ui);
  font-feature-settings: "cv02","cv03","cv04","cv11";
  font-variation-settings: "opsz" 14;
  letter-spacing: -0.008em;
}
h1, h2, h3, .modal-hdr { letter-spacing: -0.02em; font-weight: 600; }
header h1 {
  font-weight: 700;
  letter-spacing: -0.03em;
  font-size: var(--fs-lg);
}
code, pre, .usage-table td.num {
  font-family: var(--font-mono);
  font-feature-settings: "calt" 0;
}
.btn-icon {
  border-radius: var(--r-md);
  color: var(--text-dim);
  transition: background 0.15s var(--ease), color 0.15s var(--ease),
              transform 0.1s var(--ease);
}
.btn-icon svg { width: 20px; height: 20px; display: block; pointer-events: none; }
.btn-icon:hover { background: var(--bg-hover); color: var(--text); }
.btn-icon:active { transform: scale(0.92); }
#mobileMenuBtn svg, #overflowMenuBtn svg { width: 22px; height: 22px; }
#newChatBtn, .icon-btn-wide {
  border-radius: var(--r-md);
  font-weight: 500;
  letter-spacing: -0.01em;
}
#newChatBtn svg, .icon-btn-wide svg { width: 16px; height: 16px; flex-shrink: 0; }
#newChatBtn:hover, .icon-btn-wide:hover {
  background: var(--bg-active);
  border-color: var(--accent);
  color: var(--text);
}
.sess {
  border-radius: var(--r-sm);
  margin: 1px 8px;
  border-left: none !important;
  transition: background 0.15s var(--ease);
}
.sess.active {
  background: var(--bg-active) !important;
  box-shadow: inset 3px 0 0 var(--accent);
}
.sess .del svg, .sess .ren svg { width: 14px; height: 14px; display: block; }
.sess .del, .sess .ren {
  display: flex; align-items: center; justify-content: center;
  padding: 4px; border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}
.sess .del:hover, .sess .ren:hover { background: rgba(255,255,255,0.06); }
#send {
  border-radius: var(--r-xl);
  padding: 12px 16px;
  min-width: 48px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: var(--shadow-sm);
}
#send svg { width: 18px; height: 18px; display: block; }
#send:hover { background: var(--accent-hover); transform: translateY(-1px); }
#micBtn svg { width: 18px; height: 18px; display: block; }
#micBtn { border-radius: var(--r-xl); }
#input {
  border-radius: var(--r-xl);
  padding: 14px 18px;
  font-size: var(--fs-base);
  font-weight: 400;
  letter-spacing: -0.005em;
}
.msg.user { font-weight: 450; }
.msg.agent { font-weight: 400; }
.msg.step {
  font-weight: 500;
  font-size: var(--fs-xs);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.modal-hdr {
  font-weight: 600;
  letter-spacing: -0.02em;
}
.usage-card .k {
  font-weight: 600;
  letter-spacing: 0.05em;
  font-size: 11px;
}
.usage-card .v {
  font-weight: 700;
  letter-spacing: -0.03em;
  font-family: var(--font-mono);
}


/* ═══ Part 70: human-crafted density ═══
   Linear / Notion / Raycast-inspired. Structure from borders, not
   glows. Accent used once. Dense, calm, deliberate. */

body {
  background: var(--bg);
  font-size: 14px;
  letter-spacing: -0.01em;
}

/* Header — thin, structured, no decoration */
header {
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  height: 44px;
  padding: 0 12px;
  gap: 8px;
}
.header-left { gap: 8px; }
header h1 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}
.header-meta-desktop {
  gap: 12px;
  font-size: 12px;
  color: var(--text-mute);
}
.header-meta-desktop a {
  color: var(--text-dim);
  font-size: 12px;
}
.header-meta-desktop a:hover { color: var(--text); }
.badge {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  color: var(--text-mute);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, "JetBrains Mono", monospace;
  letter-spacing: 0;
}

/* Icon buttons — compact, no border, Linear-style */
.btn-icon {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--text-mute);
  font-size: 16px;
}
.btn-icon:hover {
  background: var(--bg-hover);
  border-color: var(--border);
  color: var(--text);
}
.btn-icon svg { width: 16px; height: 16px; }
#mobileMenuBtn svg, #overflowMenuBtn svg { width: 18px; height: 18px; }

/* Sidebar — thin structure, dense session list */
#sidebar {
  width: 248px;
  min-width: 248px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
}
#sidebar .sidebar-hdr {
  padding: 8px;
  gap: 4px;
  border-bottom: 1px solid var(--border);
}
#newChatBtn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  min-height: 30px;
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
}
#newChatBtn svg { width: 14px; height: 14px; }
#newChatBtn:hover {
  background: var(--bg-hover);
  border-color: var(--border-3);
  color: var(--text);
}

/* Sidebar action buttons — compact icon squares */
#exportBtn, #importBtn {
  width: 30px;
  height: 30px;
  min-width: 30px;
  min-height: 30px;
  padding: 0;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  background: transparent;
  color: var(--text-mute);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
#exportBtn:hover, #importBtn:hover {
  background: var(--bg-hover);
  border-color: var(--border-3);
  color: var(--text);
}
#exportBtn svg, #importBtn svg { width: 14px; height: 14px; }
#usageBtn.icon-btn-wide {
  padding: 0 10px;
  height: 30px;
  min-height: 30px;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  background: transparent;
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
#usageBtn svg { width: 14px; height: 14px; }
#usageBtn:hover {
  background: var(--bg-hover);
  border-color: var(--border-3);
  color: var(--text);
}

/* Session list — dense, hover reveals actions */
#sessionList { padding: 4px 0; }
.sess {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  margin: 0 4px;
  border-radius: 5px;
  font-size: 13px;
  color: var(--text-dim);
  border: 1px solid transparent;
  min-height: 28px;
  cursor: pointer;
}
.sess:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.sess.active {
  background: var(--bg-hover);
  color: var(--text);
  border-color: var(--border);
}
.sess.active::before {
  content: "";
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  width: 2px; height: 16px;
  background: var(--accent);
  border-radius: 2px;
}
.sess { position: relative; }
.sess .title { font-size: 13px; font-weight: 400; }
.sess .del, .sess .ren {
  opacity: 0;
  color: var(--text-mute);
  padding: 2px;
  border-radius: 3px;
  display: inline-flex;
  align-items: center;
}
.sess:hover .del, .sess:hover .ren { opacity: 1; }
.sess .del svg, .sess .ren svg { width: 12px; height: 12px; }
.sess .del:hover { color: var(--danger); background: rgba(248,113,113,0.1); }
.sess .ren:hover { color: var(--text); background: var(--bg-active); }

/* Chat canvas */
#chat {
  padding: 24px 20px;
  max-width: 760px;
}
.msg { margin-bottom: 16px; }
.msg.user {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 8px 8px 8px 2px;
  padding: 8px 12px;
  max-width: 88%;
  margin-left: auto;
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.55;
}
.msg.agent {
  background: transparent;
  border-left: none;
  padding: 0;
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.6;
}


.msg.step {
  font-size: 11px;
  font-weight: 500;
  text-transform: none;
  font-style: normal;
  letter-spacing: 0.01em;
  color: var(--text-faint);
  padding: 2px 0;
}

/* Composer — flat, sharp, single accent */
footer {
  padding: 12px 20px 16px;
  background: var(--bg);
  border-top: 1px solid var(--border);
}
#form {
  max-width: 760px;
  gap: 6px;
}
#input {
  background: var(--bg-input);
  border: 1px solid var(--border-2);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13.5px;
  min-height: 38px;
  color: var(--text);
}
#input:focus {
  border-color: var(--border-strong);
  box-shadow: none;
  outline: none;
}
#input::placeholder { color: var(--text-faint); }
#send {
  width: 38px;
  height: 38px;
  min-width: 38px;
  min-height: 38px;
  padding: 0;
  border-radius: 8px;
  background: var(--accent);
  color: var(--accent-ink);
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: none;
}
#send svg { width: 16px; height: 16px; }
#send:hover { background: var(--accent-hover); transform: none; box-shadow: none; }
#send:disabled { opacity: 0.4; }
#micBtn {
  width: 38px;
  height: 38px;
  min-width: 38px;
  padding: 0;
  border-radius: 8px;
  background: transparent;
  border: 1px solid var(--border-2);
  color: var(--text-mute);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
#micBtn:hover {
  border-color: var(--border-strong);
  color: var(--text);
  background: var(--bg-hover);
}
#micBtn svg { width: 16px; height: 16px; }
.footer-info {
  max-width: 760px;
  font-size: 11px;
  color: var(--text-faint);
  letter-spacing: 0.02em;
}

/* Modal — flat, structured */
.modal-panel {
  background: var(--bg-elev);
  border: 1px solid var(--border-2);
  border-radius: 10px;
  box-shadow: var(--shadow-lg);
}
.modal-hdr {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  letter-spacing: -0.01em;
}
.modal-body { padding: 16px; }
.usage-grid { gap: 8px; margin-bottom: 16px; }
.usage-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}
.usage-card .k {
  font-size: 10.5px;
  font-weight: 500;
  color: var(--text-mute);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.usage-card .v {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  margin-top: 4px;
  letter-spacing: -0.02em;
  font-family: inherit;
}
.usage-table { font-size: 12.5px; }
.usage-table th {
  background: transparent;
  color: var(--text-mute);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
  padding: 8px 10px;
}
.usage-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-dim);
}
.usage-table td.num {
  font-family: ui-monospace, "JetBrains Mono", monospace;
  color: var(--text);
}
.usage-table tr:hover td { background: var(--bg-hover); }
.usage-h {
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
  margin: 16px 0 8px;
  letter-spacing: -0.01em;
}

/* Overflow panel — flat */
.overflow-panel {
  background: var(--bg-elev);
  border: 1px solid var(--border-2);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  padding: 4px;
  min-width: 200px;
}
.overflow-panel a,
.overflow-panel button {
  padding: 7px 10px;
  border-radius: 5px;
  font-size: 13px;
  color: var(--text-dim);
}
.overflow-panel a:hover,
.overflow-panel button:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.overflow-panel .badge {
  margin: 4px 10px;
  font-size: 11px;
}

/* Mobile drawer keeps glass but tighter */
@media (max-width: 640px) {
  :root { --header-h: 44px; }
  #sidebar {
    width: min(260px, 82vw);
    min-width: min(260px, 82vw);
    background: var(--bg);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border-right: 1px solid var(--border-2);
    box-shadow: 4px 0 24px rgba(0,0,0,0.6);
  }
  .overlay-backdrop {
    background: rgba(0,0,0,0.55);
    -webkit-backdrop-filter: blur(2px);
    backdrop-filter: blur(2px);
  }
  #chat { padding: 16px 14px; }
  footer { padding: 10px 12px 14px; }
  .modal-overlay { padding: 12px; }
  .modal-panel { border-radius: 10px; }
}

/* Scrollbars — subtle */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border-3);
  border-radius: 4px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--border-strong);
  background-clip: padding-box;
}

::selection { background: rgba(74,222,128,0.25); color: var(--text); }
<
/* ═══ Part 71: matches ChatGPT/Claude conventions ═══ */

/* User message — right-aligned bubble, no text label */
.msg.user {
  max-width: 82%;
  margin-left: auto;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 14px 14px 4px 14px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.55;
}

/* Agent message — plain text, no border, wider */
.msg.agent {
  max-width: 100%;
  margin-right: auto;
  padding: 0;
  background: transparent;
  border: none;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text);
}

/* Spacing between turns */
.msg + .msg { margin-top: 20px; }
.msg.user + .msg.agent { margin-top: 16px; }
.msg.agent + .msg.user { margin-top: 24px; }

/* Empty state — friendly, not italic */
#chat:empty::before,
#chat > .msg.step:first-child {
  display: block;
  color: var(--text-mute);
  font-size: 13px;
  font-style: normal;
  text-align: center;
  padding: 60px 20px;
  letter-spacing: 0;
}

/* Sidebar grouping (Today / Yesterday / Older) */
.sess-group-hdr {
  padding: 12px 14px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  user-select: none;
}
.sess-group-hdr:first-child { padding-top: 8px; }

/* Search in sidebar */
#sessSearch {
  width: calc(100% - 16px);
  margin: 8px;
  padding: 6px 10px 6px 30px;
  min-height: 30px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 12.5px;
  font-family: inherit;
  outline: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%236e6e76' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='11' cy='11' r='8'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg>");
  background-repeat: no-repeat;
  background-position: 10px center;
}
#sessSearch:focus { border-color: var(--border-strong); }
#sessSearch::placeholder { color: var(--text-faint); }

/* Composer — slightly more confident */
footer { padding: 14px 20px 18px; }
#input {
  padding: 12px 16px;
  min-height: 42px;
  font-size: 14px;
  border-radius: 10px;
}
#send {
  width: 42px;
  height: 42px;
  min-width: 42px;
  min-height: 42px;
  border-radius: 10px;
}
#micBtn {
  width: 42px;
  height: 42px;
  min-width: 42px;
  border-radius: 10px;
}

/* ═════ Part 93: professional header redesign ═════ */
header { gap: var(--sp-2); padding: 0 var(--sp-3); height: 56px; }
.brand {
  display: inline-flex; align-items: center; gap: 9px;
  margin: 0; font-size: 15px; font-weight: 700;
  letter-spacing: -0.01em; color: var(--text); min-width: 0;
}
.brand-mark {
  width: 26px; height: 26px; border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2, #22d3ee));
  color: #0a0a0b; font-weight: 800; font-size: 14px;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0; letter-spacing: 0;
  box-shadow: 0 2px 10px rgba(74,222,128,0.22);
}
.brand-name { font-size: 15px; font-weight: 600; color: var(--text); white-space: nowrap; }
.session-pill {
  display: inline-flex; align-items: center; gap: 7px;
  margin-left: 6px; padding: 4px 11px; border-radius: 999px;
  background: var(--bg-hover); border: 1px solid var(--border);
  font-size: 12px; color: var(--text-dim);
  max-width: 240px; min-width: 0;
}
.session-pill #sid {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;
}
.session-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 8px rgba(74,222,128,0.65);
  flex-shrink: 0;
}
.header-right { gap: 4px; }
.icon-btn {
  width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 9px; background: transparent; border: none;
  color: var(--text-dim); cursor: pointer; position: relative;
  text-decoration: none; padding: 0;
  transition: background 0.14s ease, color 0.14s ease, transform 0.08s ease;
  -webkit-tap-highlight-color: transparent;
}
.icon-btn:hover { background: var(--bg-hover); color: var(--text); }
.icon-btn:active { transform: scale(0.94); }
.icon-btn svg { display: block; }
.icon-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.pill-badge {
  position: absolute; top: 3px; right: 3px;
  min-width: 15px; height: 15px; padding: 0 4px; border-radius: 8px;
  background: var(--accent); color: #0a0a0b;
  font-size: 9.5px; font-weight: 700; line-height: 15px; text-align: center;
  border: 2px solid var(--bg-elev); box-sizing: content-box;
  font-family: inherit;
}
.pill-badge:empty { display: none; }
.provider-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; margin-right: 4px; border-radius: 999px;
  background: rgba(74,222,128,0.08); border: 1px solid rgba(74,222,128,0.24);
  color: var(--accent); font-size: 11px; font-weight: 500;
  letter-spacing: 0.01em; white-space: nowrap;
}
.provider-pill:empty { display: none !important; }
.provider-pill::before {
  content: ''; width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 6px var(--accent); flex-shrink: 0;
}
.overflow-wrap { position: relative; }
.overflow-panel {
  position: absolute; top: calc(100% + 10px); right: 0;
  min-width: 240px; background: var(--bg-elev);
  border: 1px solid var(--border-2); border-radius: 12px; padding: 6px;
  box-shadow: 0 20px 44px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.02);
  z-index: 1000; display: none; animation: menuIn 0.14s ease;
}
.overflow-wrap.open .overflow-panel,
.overflow-panel.open { display: block; }
@keyframes menuIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.overflow-head { padding: 8px 10px 6px; }
.overflow-label {
  font-size: 10px; font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--text-mute); margin-bottom: 3px;
}
.overflow-value {
  font-size: 12.5px; color: var(--text-dim);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.overflow-item {
  display: flex; align-items: center; gap: 11px;
  padding: 9px 10px; border-radius: 8px;
  color: var(--text); font-size: 13px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  background: none; border: none; width: 100%; text-align: left;
  font-family: inherit;
  transition: background 0.1s ease, color 0.1s ease;
}
.overflow-item:hover { background: var(--bg-hover); color: var(--text); }
.overflow-item svg { color: var(--text-mute); flex-shrink: 0; transition: color 0.1s ease; }
.overflow-item:hover svg { color: var(--accent); }
.overflow-divider { height: 1px; background: var(--border); margin: 5px 4px; }
.overflow-meta {
  display: block; padding: 5px 10px 2px;
  font-size: 11px; color: var(--text-mute);
}
.overflow-meta:empty { display: none; }
@media (max-width: 760px) {
  .brand-name { display: none; }
  .session-pill { max-width: 140px; font-size: 11px; padding: 3px 9px; }
}
@media (max-width: 480px) {
  .session-pill { display: none; }
  .icon-btn { width: 34px; height: 34px; }
}


/* === Part 93b: paperclip inside composer === */
.composer-input {
  flex: 1; min-width: 0; position: relative;
  display: flex; align-items: center;
}
.composer-input #input {
  flex: 1; width: 100%;
  padding-left: 46px;
}
.attach-btn {
  position: absolute; left: 5px; top: 50%;
  transform: translateY(-50%);
  width: 34px; height: 34px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; background: transparent; border: none;
  color: var(--text-mute); cursor: pointer;
  text-decoration: none; padding: 0;
  transition: background 0.14s ease, color 0.14s ease, transform 0.08s ease;
  -webkit-tap-highlight-color: transparent;
}
.attach-btn:hover { background: var(--bg-hover); color: var(--text); }
.attach-btn:active { transform: translateY(-50%) scale(0.92); }
.attach-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.attach-btn svg { display: block; }
.attach-btn .pill-badge {
  top: -2px; right: -2px;
  min-width: 15px; height: 15px;
  padding: 0 4px;
  line-height: 15px;
  font-size: 9.5px;
  border-width: 2px;
  border-color: var(--bg, #0c0c0d);
  box-shadow: 0 0 0 1px rgba(0,0,0,0.35);
}
@media (max-width: 480px) {
  .attach-btn { width: 30px; height: 30px; left: 4px; }
  .attach-btn svg { width: 16px; height: 16px; }
  .composer-input #input { padding-left: 40px; }
}


/* === Part 95: sidebar footer + upward-opening menu === */
#sidebar { display: flex; flex-direction: column; }
#sessionList { flex: 1; overflow-y: auto; }
.sidebar-footer {
  padding: var(--sp-2);
  border-top: 1px solid var(--border);
  background: var(--bg-sidebar);
  flex-shrink: 0;
}
.sidebar-menu-btn {
  width: 100%;
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 9px;
  background: transparent; border: none;
  color: var(--text-dim); cursor: pointer;
  font-size: 13px; font-weight: 500; font-family: inherit;
  transition: background 0.14s ease, color 0.14s ease;
  text-align: left;
}
.sidebar-menu-btn:hover { background: var(--bg-hover); color: var(--text); }
.sidebar-menu-btn svg { flex-shrink: 0; transition: transform 0.4s ease; }
.sidebar-menu-btn:hover svg { transform: rotate(90deg); }
.sidebar-menu-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Menu opens UPWARD from bottom-left */
.sidebar-footer .overflow-panel {
  top: auto;
  bottom: calc(100% + 8px);
  right: auto;
  left: var(--sp-2);
  min-width: 240px;
  animation: menuInUp 0.14s ease;
}
@keyframes menuInUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (max-width: 640px) {
  .sidebar-menu-label { display: none; }
  .sidebar-menu-btn { justify-content: center; padding: 10px; }
}


  /* Part 104: provider health panel */
  .ph-section { margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
  .ph-title { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-mute); margin-bottom: 8px; }
  .ph-summary { font-size: 13px; color: var(--text-dim); margin-bottom: 10px; }
  .ph-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .ph-table th { text-align: left; font-weight: 500; color: var(--text-mute); padding: 6px 8px; border-bottom: 1px solid var(--border); font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em; }
  .ph-table td { padding: 7px 8px; border-bottom: 1px solid var(--border); color: var(--text); }
  .ph-table tbody tr:last-child td { border-bottom: none; }
  .ph-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .ph-dot.ready { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
  .ph-dot.cooling { background: #ffb020; box-shadow: 0 0 6px #ffb020; }
  .ph-foot { font-size: 11.5px; color: var(--text-mute); margin-top: 7px; }
  .ph-empty { color: var(--text-mute); font-size: 13px; }


  /* Part 105: per-message provider chip */
  .provider-chip {
    font-size: 11px;
    color: var(--text-mute);
    padding-left: calc(var(--sp-3) + 3px);
    margin-top: -4px;
    margin-bottom: var(--sp-3);
    letter-spacing: 0.02em;
    opacity: 0.7;
    user-select: none;
  }

</style>
</head>
<body>
<header>
  <div class="header-left">
    <button id="mobileMenuBtn" class="btn-icon" type="button" title="Menu" aria-label="Open menu">&#9776;</button>
    <h1 class="brand">
      <span class="brand-mark" aria-hidden="true">S</span>
      <span class="brand-name">Sunnyware</span>
    </h1>
    <span class="session-pill" title="Current session">
      <span class="session-dot" aria-hidden="true"></span>
      <span id="sid">New chat</span>
    </span>
  </div>
  <div class="header-right">
    <select id="roleSelect" title="Role persona" aria-label="Role persona">
      <option value="general">✨ General</option>
      <option value="fpa">📊 FP&amp;A Analyst</option>
      <option value="quant">🧮 Quant Researcher</option>
      <option value="actuary">🏦 Actuarial Analyst</option>
      <option value="tax">🧾 Tax Accountant</option>
      <option value="cfo">💼 Chief Financial Officer</option>
      <option value="cdo">📋 Chief Delivery Officer</option>
      <option value="legal">⚖️ Financial Legal Assistant</option>
      <option value="risk_ins">🛡️ Financial Risk & Insurance</option>
    </select>
    <span id="providerBadge" class="provider-pill" title="Serving provider"></span>
  </div>
</header>
<input type="file" id="fileInput" multiple
       accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls">
<div id="usageModal" class="modal-overlay" style="display:none">
  <div class="modal-panel">
    <div class="modal-hdr">
      <span>Stats &amp; Provider Health</span>
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
    <input type="text" id="sessSearch" placeholder="Search sessions…" autocomplete="off">
<div id="sessionList"></div>
    <div class="sidebar-footer">
      <div class="overflow-wrap">
        <button id="overflowMenuBtn" class="sidebar-menu-btn" type="button" title="Settings & more" aria-label="Settings & more">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <span class="sidebar-menu-label">Settings &amp; more</span>
        </button>
        <div class="overflow-panel" id="overflowPanel">
          <div class="overflow-head">
            <div class="overflow-label">Current session</div>
            <div class="overflow-value" id="sidMobile">New chat</div>
          </div>
          <div class="overflow-divider"></div>
          <a href="/about" target="_blank" rel="noopener" class="overflow-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            <span>About</span>
          </a>
          <a href="/docs" target="_blank" rel="noopener" class="overflow-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>API Documentation</span>
          </a>
          <div class="overflow-divider"></div>
          <a href="#" id="uploadMobile" class="overflow-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>Upload files</span>
          </a>
          <a href="#" id="clearMobile" class="overflow-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>New session</span>
          </a>
          <span class="overflow-meta" id="docCountMobile" aria-hidden="true"></span>
          <span class="overflow-meta" id="providerBadgeMobile" aria-hidden="true"></span>
        </div>
      </div>
    </div>
  </aside>
  <div id="main">
    <div id="chat"></div>
    <footer>
      <form id="form">
        <div class="composer-input">
          <a href="#" id="upload" class="attach-btn" title="Upload files" aria-label="Upload files">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
            <span class="pill-badge" id="docCount" aria-hidden="true"></span>
          </a>
          <input type="text" id="input" placeholder="Ask anything..." autocomplete="off" required>
        </div>
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
  const clearBtn = document.getElementById('clear') || document.getElementById('newChatBtn');

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

  // ── Part 112: role persona helpers ──
  const ROLE_KEY = 'sunnyware.role';
  function getRole() {
    try { return localStorage.getItem(ROLE_KEY) || 'general'; }
    catch (e) { return 'general'; }
  }
  function setRole(v) {
    const r = (v || 'general').toString().toLowerCase();
    try { localStorage.setItem(ROLE_KEY, r); } catch (e) {}
  }
  async function persistRoleToSession(role) {
    try {
      const sid = getSession();
      if (!sid) return;
      await fetch('/api/sessions/' + encodeURIComponent(sid) + '/role', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role }),
      });
      // Part 113B: reflect role color immediately
      const _chat = document.getElementById('chat');
      if (_chat) _chat.dataset.role = role;
    } catch (e) { /* best-effort */ }
  }

  async function syncRoleFromSession(sid) {
    try {
      if (!sid) return;
      const r = await fetch(
        '/api/sessions/' + encodeURIComponent(sid) + '/role',
        { cache: 'no-store' }
      );
      if (!r.ok) return;
      const d = await r.json();
      if (d && d.role) {
        setRole(d.role);
        const sel = document.getElementById('roleSelect');
        if (sel) sel.value = d.role;
        // Part 113B: sync chat container role styling
        const _chat = document.getElementById('chat');
        if (_chat) _chat.dataset.role = d.role;
      }
    } catch (e) { /* best-effort */ }
  }

  function initRoleSelector() {
    const sel = document.getElementById('roleSelect');
    if (!sel) return;
    sel.value = getRole();
    // Part 113B: apply session role on boot
    const _chat = document.getElementById('chat');
    if (_chat) _chat.dataset.role = getRole();
    sel.addEventListener('change', () => {
      setRole(sel.value);
      persistRoleToSession(sel.value);   // Part 113A
    });
    // Sync options from server (best-effort)
    fetch('/api/roles', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d || !Array.isArray(d.roles)) return;
        const current = sel.value;
        sel.innerHTML = '';
        for (const r of d.roles) {
          const o = document.createElement('option');
          o.value = r.key;
          o.textContent = (r.icon ? r.icon + ' ' : '') + r.label;
          sel.appendChild(o);
        }
        sel.value = current || d.default || 'general';
      })
      .catch(() => {});
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
    sidEl.textContent = getSession();
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
          // Part 106c: strip broken base64 markdown + carry attachments
          var _clean = content.replace(
            /!\[[^\]]*\]\(data:image\/[^)]*\[image: \d+ bytes base64\]\)/g,
            ''
          ).trim();
          var _atts = (payload && payload.attachments) || [];
          messages.push({ role: 'agent', text: _clean, ts: ts,
                          attachments: _atts });
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
      // Part 170: prefer custom title from metadata.title
      var _stored_title = '';
      try {
        var _m = (typeof s.metadata === 'string')
                 ? JSON.parse(s.metadata) : (s.metadata || {});
        if (_m && _m.title) _stored_title = String(_m.title).slice(0, 60);
      } catch (e) { /* silent */ }
      let title = _stored_title || 'New chat';
      if (!_stored_title) {
        for (let j = 0; j < msgs.length; j++) {
          if (msgs[j].role === 'user' && msgs[j].text) {
            title = msgs[j].text.length > 40
              ? msgs[j].text.slice(0, 40) : msgs[j].text;
            break;
          }
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
    syncRoleFromSession(id);   // Part 113A
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
        const _bubble = addMsg(m.text, m.role, false);
        // Part 106c: render stored attachments below the bubble
        if (m.attachments && m.attachments.length && _bubble) {
          for (const a of m.attachments) {
            if (!a || !a.url) continue;
            try {
              const _img = document.createElement('img');
              _img.src = a.url;
              _img.className = 'msg-image';
              _img.loading = 'lazy';
              _img.alt = 'generated image';
              _bubble.insertAdjacentElement('afterend', _img);
            } catch (err) { /* silent */ }
          }
        }
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
    // Part 170: persist to backend (best-effort, fire-and-forget)
    try {
      fetch('/api/sessions/' + encodeURIComponent(id) + '/title', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: sess.title })
      }).catch(function(){});
    } catch (e) { /* silent */ }
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

  // ── Part 123: interactive Plotly chart renderer ──
  var _plotlyRenderScheduled = false;
  function _renderPendingPlotly() {
    _plotlyRenderScheduled = false;
    var els = document.querySelectorAll(
      '.sunnyware-plotly:not([data-plotly-rendered])'
    );
    if (!els || !els.length) return;
    if (typeof Plotly === 'undefined') {
      for (var k = 0; k < els.length; k++) {
        els[k].setAttribute('data-plotly-rendered', '1');
        els[k].textContent = '[interactive chart unavailable]';
        els[k].style.cssText = 'padding:8px;color:#888;font-style:italic';
      }
      return;
    }
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      try {
        var b64 = el.getAttribute('data-plotly-b64');
        el.setAttribute('data-plotly-rendered', '1');
        if (!b64) continue;
        var spec = JSON.parse(atob(b64));
        Plotly.newPlot(el, spec.data || [], spec.layout || {}, {
          responsive: true, displayModeBar: false,
          margin: { l: 50, r: 20, t: 40, b: 40 },
        });
        el.style.cssText = 'min-height:320px;max-width:100%;margin:8px 0';
      } catch (e) {
        el.textContent = '[chart render error]';
        el.style.cssText = 'padding:8px;color:#c66;font-style:italic';
      }
    }
  }
  function _schedulePlotlyRender() {
    if (_plotlyRenderScheduled) return;
    _plotlyRenderScheduled = true;
    setTimeout(_renderPendingPlotly, 0);
    setTimeout(_renderPendingPlotly, 250);
  }

  function renderAgentHtml(text) {
    if (!text) return '';
    if (typeof marked === 'undefined' || !marked.parse) return escapeHtml(text);
    try {
      var raw = marked.parse(wrapBareBase64(text));
      raw = raw.split('<\/script').join('&lt;/script');
      raw = raw.split('javascript:').join('');
      if (raw.indexOf('sunnyware-plotly') >= 0) {
        _schedulePlotlyRender();
      }
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
    let streamError = '';  // Part 88: surface backend error instead of blank bubble
    let budgetExceeded = false;  // Part 91: mark bubble if budget guard tripped
    let lastProvider = '';       // Part 105: track provider for the trailing chip
    let lastAttachments = [];    // Part 106c: track attachment refs for storage

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
      const r = await fetch('/api/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: text, session_id: getSession(), role: getRole() }),
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
            // Part 113B: apply role identity to chat container
            if (data.role) {
              chat.dataset.role = data.role;
              if (data.accent) chat.style.setProperty('--role-accent', data.accent);
            }
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
            } else if (type === 'tool_result') {
              // Part 98c: render image_base64 results inline
              const _r = data.result || {};
              if (_r.image_base64 && _r.image_format) {
                const _img = document.createElement('img');
                _img.src = 'data:image/' + _r.image_format + ';base64,' + _r.image_base64;
                _img.className = 'msg-image';
                _img.alt = (_r.prompt || _r.title || 'generated image').slice(0, 120);
                _img.loading = 'lazy';
                chat.appendChild(_img);
                chat.scrollTop = chat.scrollHeight;
              }
            } else if (type === 'budget_exceeded') {
              budgetExceeded = true;  // Part 91: style the final bubble
            } else if (type === 'error') {
              addMsg('error: ' + (data.error || data.text || 'unknown'), 'error');
            } else if (type === 'final') {
              // Tool-aware endpoint: final carries assembled answer + provider
              const ans = data.answer || '';
              if (data.attachments && data.attachments.length) {
                lastAttachments = data.attachments;  // Part 106c
              }
              if (data.budget_exceeded) budgetExceeded = true;  // Part 91
              if (ans) {
                agentText = ans;
                const _fbub = ensureBubble();
                _fbub.innerHTML = renderAgentHtml(agentText);
                if (budgetExceeded) _fbub.classList.add('budget');
                chat.scrollTop = chat.scrollHeight;
              } else if (data.ok === false && data.error) {
                // Part 88: backend reported failure -- remember it for end-of-stream
                streamError = String(data.error);
              }
              if (data.provider) {
                lastProvider = data.provider;  // Part 105
                const pb = document.getElementById('providerBadge');
                if (pb) pb.textContent = 'via ' + data.provider;
              }
            } else if (type === 'done') {
              if (data.provider) {
                lastProvider = data.provider;  // Part 105
                const pb = document.getElementById('providerBadge');
                if (pb) pb.textContent = 'via ' + data.provider;
              }
            }
          }
        }
      }

      const ms = Math.round(performance.now() - t0);
      latEl.textContent = ms + ' ms';

      // Part 105: append provider chip under the assistant bubble
      if (agentBubble && lastProvider) {
        try {
          const _chip = document.createElement('div');
          _chip.className = 'provider-chip';
          _chip.textContent = 'via ' + lastProvider
                              + ' · ' + (ms / 1000).toFixed(1) + 's';
          agentBubble.insertAdjacentElement('afterend', _chip);
        } catch (e) { /* silent */ }
      }

      // Part 106c: persist attachments on the last stored agent message.
      // Part 106d: if the LLM returned no text after a tool call, no
      // agent bubble exists -- create one so the image has a home.
      if (lastAttachments && lastAttachments.length) {
        try {
          var _ss = getSessions();
          var _sid = getActiveId();
          if (!_ss[_sid]) {
            _ss[_sid] = { id: _sid, title: 'New chat',
                          created: Date.now(), messages: [] };
          }
          var _sess = _ss[_sid];
          if (!_sess.messages) _sess.messages = [];

          // Ensure agent bubble exists in DOM so we can attach image
          var _ab = ensureBubble();
          // If the agent bubble has no text, add a placeholder so the
          // session survives reload with a visible assistant message.
          if (!agentText) {
            agentText = 'Image generated.';
            try {
              _ab.innerHTML = renderAgentHtml('<em>(image attached)</em>');
            } catch (e) { /* silent */ }
          }

          // Find/create the agent message that corresponds to this turn
          var _last = _sess.messages.length
                      ? _sess.messages[_sess.messages.length - 1] : null;
          if (_last && _last.role === 'agent'
              && (!_last.text || _last.text === agentText)) {
            _last.attachments = lastAttachments;
            if (!_last.text) _last.text = agentText;
          } else if (_last && _last.role === 'agent') {
            // old agent message from previous turn, do not overwrite
            // create a fresh message instead
            _sess.messages.push({
              role: 'agent', text: agentText,
              ts: Date.now(), attachments: lastAttachments
            });
          } else {
            // last is user (or session empty) -- append a new agent msg
            _sess.messages.push({
              role: 'agent', text: agentText,
              ts: Date.now(), attachments: lastAttachments
            });
          }
          saveSessions(_ss);
        } catch (e) { /* silent */ }
      }

      if (!agentText) {
        if (streamError) {
          addMsg('⚠️ ' + streamError, 'error');  // Part 88
        } else {
          addMsg('(empty response)', 'error');
        }
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

  // Part 40 + Part 104: stats dashboard with provider health
  var _phRefreshTimer = null;

  function _startPHRefresh() {
    if (_phRefreshTimer) clearInterval(_phRefreshTimer);
    _phRefreshTimer = setInterval(async () => {
      const m = document.getElementById('usageModal');
      if (!m || m.style.display === 'none') return;
      try {
        const r = await fetch('/api/providers/metrics');
        const metrics = await r.json();
        const old = document.getElementById('providerHealthSection');
        if (old && old.parentNode) {
          old.parentNode.replaceChild(renderProviderHealth(metrics), old);
        }
      } catch (e) { /* silent */ }
    }, 10000);
  }

  function _stopPHRefresh() {
    if (_phRefreshTimer) {
      clearInterval(_phRefreshTimer);
      _phRefreshTimer = null;
    }
  }

  async function openUsageModal() {
    const modal = document.getElementById('usageModal');
    if (!modal) return;
    modal.style.display = 'flex';
    const body = document.getElementById('usageBody');
    body.innerHTML = '';
    const loading = document.createElement('div');
    loading.className = 'usage-loading';
    loading.textContent = 'Loading...';
    body.appendChild(loading);
    try {
      const results = await Promise.all([
        fetch('/api/usage'),
        fetch('/api/usage/pricing'),
        fetch('/api/providers/metrics'),
      ]);
      const usage = await results[0].json();
      const pricing = await results[1].json();
      let metrics = null;
      try { metrics = await results[2].json(); } catch (e) { metrics = null; }
      renderUsageDashboard(usage, pricing);
      const ph = renderProviderHealth(metrics);
      body.insertBefore(ph, body.firstChild);
      _startPHRefresh();
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
    _stopPHRefresh();
  }

  function renderProviderHealth(metrics) {
    const sec = document.createElement('div');
    sec.className = 'ph-section';
    sec.id = 'providerHealthSection';

    const h = document.createElement('div');
    h.className = 'ph-title';
    h.textContent = 'Provider Health';
    sec.appendChild(h);

    if (!metrics || metrics.error) {
      const err = document.createElement('div');
      err.className = 'ph-empty';
      err.textContent = 'Unavailable';
      sec.appendChild(err);
      return sec;
    }

    const sum = metrics.summary || {};
    const summ = document.createElement('div');
    summ.className = 'ph-summary';
    const pc = sum.total_providers || 0;
    const ready = sum.ready || 0;
    const cooling = sum.cooling || 0;
    const sRate = sum.session_success_rate;
    const rateStr = (sRate === null || sRate === undefined)
                    ? 'n/a'
                    : (sRate * 100).toFixed(1) + '%';
    summ.textContent = pc + ' providers | ' + ready + ' ready | '
                       + cooling + ' cooling | session rate ' + rateStr;
    sec.appendChild(summ);

    const tbl = document.createElement('table');
    tbl.className = 'ph-table';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    ['Provider', 'Model', 'Status', 'Rate'].forEach(function(txt) {
      const th = document.createElement('th');
      th.textContent = txt;
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    tbl.appendChild(thead);

    const tbody = document.createElement('tbody');
    (metrics.providers || []).forEach(function(p) {
      const tr = document.createElement('tr');

      const td1 = document.createElement('td');
      td1.textContent = p.name;
      tr.appendChild(td1);

      const td2 = document.createElement('td');
      const mdl = (p.model || '').replace(/^.*\//, '');
      td2.textContent = mdl.length > 22 ? mdl.slice(0, 22) + '..' : mdl;
      td2.title = p.model || '';
      tr.appendChild(td2);

      const td3 = document.createElement('td');
      const dot = document.createElement('span');
      dot.className = 'ph-dot ' + (p.cooling ? 'cooling' : 'ready');
      td3.appendChild(dot);
      td3.appendChild(document.createTextNode(p.cooling ? 'cooling' : 'ready'));
      tr.appendChild(td3);

      const td4 = document.createElement('td');
      const sr = p.session && p.session.success_rate;
      if (sr === null || sr === undefined) {
        td4.textContent = 'n/a';
      } else {
        td4.textContent = (sr * 100).toFixed(1) + '%';
      }
      tr.appendChild(td4);

      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    sec.appendChild(tbl);

    const st = metrics.storage && metrics.storage.provider_limits;
    if (st) {
      const foot = document.createElement('div');
      foot.className = 'ph-foot';
      const parts = [];
      if (st.path_source) parts.push('storage: ' + st.path_source);
      const learned = st.learned || {};
      const lk = Object.keys(learned);
      if (lk.length) {
        parts.push('learned: ' + lk.map(function(k) { return k + '=' + learned[k]; }).join(', '));
      }
      foot.textContent = parts.join(' | ');
      sec.appendChild(foot);
    }

    const lt = document.createElement('div');
    lt.className = 'ph-foot';
    lt.textContent = 'Lifetime: ' + (sum.lifetime_attempts_total || 0) + ' attempts | '
                     + (sum.lifetime_empty_total || 0) + ' empty | '
                     + (sum.lifetime_learned_total || 0) + ' learned | '
                     + (sum.retries_total || 0) + ' retries';
    sec.appendChild(lt);

    return sec;
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

  if (clearBtn) {
    clearBtn.addEventListener('click', (e) => {
      e.preventDefault();
      createNewSession();
    });
  }

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
      // Part 94: just the number as a small badge (ChatGPT-style)
      var _n = d.count || 0;
      docCountEl.textContent = _n > 0 ? String(_n) : '';
    } catch (e) {
      docCountEl.textContent = '';
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
      createNewSession();
      renderSidebar();
    }
    // Part 64: ALWAYS hydrate from Neon (previously only ran when
    // localStorage was empty). This restores cross-device history even
    // when this browser already has cached sessions.
    hydrateFromNeon().then((merged) => {
      if (merged > 0) {
        renderSidebar();
      }
    }).catch(() => { /* silently ignore offline */ });
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


  // ── Part 65: device class + overflow menu ──
  

  

// Part 67: device detection
(function initDevice67() {
  function detect() {
    try {
      var w = window.innerWidth;
      var ua = navigator.userAgent || "";
      var tvSigns = ["SmartTV","Tizen","Web0S","WebOS","NetCast","HbbTV","Viera","BRAVIA","AquosBrowser","SMART-TV","AppleTV","CrKey","FireTV","AFT"];
      var isTV = false;
      for (var i = 0; i < tvSigns.length; i++) { if (ua.indexOf(tvSigns[i]) !== -1) { isTV = true; break; } }
      var cls = "device-desktop";
      if (isTV) cls = "device-tv";
      else if (w < 641) cls = "device-mobile";
      else if (w < 901) cls = "device-tablet";
      else if (w < 1400) cls = "device-laptop";
      var all = ["device-mobile","device-tablet","device-laptop","device-desktop","device-tv"];
      for (var j = 0; j < all.length; j++) document.body.classList.remove(all[j]);
      document.body.classList.add(cls);
      if ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0) { document.body.classList.add("has-touch"); }
    } catch (e) {}
  }
  detect();
  var _t = null;
  window.addEventListener("resize", function () { if (_t) clearTimeout(_t); _t = setTimeout(detect, 120); });
  window.addEventListener("orientationchange", function () { setTimeout(detect, 150); });
})();

// Part 67: mobile drawer (delegated, capture phase)
(function initDrawer67() {
  function open()  { document.body.classList.add('mobile-menu-open'); }
  function close() { document.body.classList.remove('mobile-menu-open'); }
  function isOpen() { return document.body.classList.contains('mobile-menu-open'); }
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#mobileMenuBtn')) { e.preventDefault(); e.stopImmediatePropagation(); if (isOpen()) close(); else open(); return; }
    if (t.closest('#overlayBackdrop')) { e.preventDefault(); e.stopImmediatePropagation(); close(); return; }
    if (t.closest('.sess')) { close(); return; }
    if (isOpen() && !t.closest('#sidebar')) close();
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && isOpen()) close(); });
})();

// Part 67: overflow panel
(function initOverflow67() {
  var panel = document.getElementById('overflowPanel');
  if (!panel) return;
  function closePanel() { panel.classList.remove('open'); }
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#overflowMenuBtn')) { e.preventDefault(); e.stopImmediatePropagation(); panel.classList.toggle('open'); return; }
    if (!panel.classList.contains('open')) return;
    if (t.closest('.overflow-panel')) return;
    closePanel();
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePanel(); });
  var upMobile = document.getElementById('uploadMobile');
  var upDesk   = document.getElementById('upload');
  if (upMobile && upDesk) { upMobile.addEventListener('click', function (e) { e.preventDefault(); upDesk.click(); closePanel(); }); }
  var clMobile = document.getElementById('clearMobile');
  var clTarget = document.getElementById('newChatBtn') || document.getElementById('clear');
  if (clMobile && clTarget) { clMobile.addEventListener('click', function (e) { e.preventDefault(); clTarget.click(); closePanel(); }); }
})();

// Part 67: sync mobile meta
(function syncMeta67() {
  var pairs = [['sid','sidMobile'],['docCount','docCountMobile'],['providerBadge','providerBadgeMobile']];
  function syncOne(a, b) {
    var src = document.getElementById(a);
    var dst = document.getElementById(b);
    if (!src || !dst) return;
    if (dst.textContent !== src.textContent) dst.textContent = src.textContent;
  }
  function syncAll() { pairs.forEach(function (p) { syncOne(p[0], p[1]); }); }
  if (window.MutationObserver) {
    pairs.forEach(function (p) {
      var src = document.getElementById(p[0]);
      if (src) { new MutationObserver(syncAll).observe(src, { characterData: true, childList: true, subtree: true }); }
    });
  }
  setInterval(syncAll, 1200);
})();
// ═══ Part 68: Lucide-style SVG icon set ═══
(function initIcons68() {
  var S = 'xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  var I = {
    menu:    '<svg '+S+'><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>',
    more:    '<svg '+S+'><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="5" r="1.2" fill="currentColor"/><circle cx="12" cy="19" r="1.2" fill="currentColor"/></svg>',
    plus:    '<svg '+S+'><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    download:'<svg '+S+'><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    upload:  '<svg '+S+'><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    chart:   '<svg '+S+'><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
    mic:     '<svg '+S+'><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>',
    send:    '<svg '+S+'><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    trash:   '<svg '+S+'><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    pencil:  '<svg '+S+'><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    x:       '<svg '+S+'><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
  };
  window.__ICONS = I;

  function applyStatic() {
    var ids = { mobileMenuBtn:'menu', overflowMenuBtn:'more',
                exportBtn:'download', importBtn:'upload',
                micBtn:'mic', usageClose:'x' };
    for (var id in ids) {
      var el = document.getElementById(id);
      if (el && I[ids[id]]) el.innerHTML = I[ids[id]];
    }
    var nc = document.getElementById('newChatBtn');
    if (nc && !nc.querySelector('svg'))
      nc.innerHTML = I.plus + '<span style="margin-left:6px">New chat</span>';
    var ub = document.getElementById('usageBtn');
    if (ub && !ub.querySelector('svg'))
      ub.innerHTML = I.chart + '<span style="margin-left:6px">Stats</span>';
    var sb = document.getElementById('send');
    if (sb && !sb.querySelector('svg'))
      sb.innerHTML = I.send;
  }

  function applySessIcons() {
    var dels = document.querySelectorAll('.sess .del');
    var rens = document.querySelectorAll('.sess .ren');
    for (var i = 0; i < dels.length; i++)
      if (!dels[i].querySelector('svg')) dels[i].innerHTML = I.trash;
    for (var j = 0; j < rens.length; j++)
      if (!rens[j].querySelector('svg')) rens[j].innerHTML = I.pencil;
  }

  function boot() {
    applyStatic();
    applySessIcons();
    var sl = document.getElementById('sessionList');
    if (sl && window.MutationObserver) {
      new MutationObserver(applySessIcons).observe(sl, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
    document.addEventListener('DOMContentLoaded', initRoleSelector);
  } else {
    setTimeout(boot, 50);
  }
  setTimeout(boot, 800);
  setTimeout(boot, 2000);
})();

// ═══ Part 71: sidebar session grouping ═══
(function initSessGrouping71() {
  function group() {
    var list = document.getElementById('sessionList');
    if (!list) return;
    // Ensure search input wires once
    var search = document.getElementById('sessSearch');
    if (search && !search._wired) {
      search._wired = true;
      search.addEventListener('input', function () {
        var q = (search.value || '').toLowerCase();
        var rows = list.querySelectorAll('.sess');
        for (var i = 0; i < rows.length; i++) {
          var t = (rows[i].textContent || '').toLowerCase();
          rows[i].style.display = q && t.indexOf(q) === -1 ? 'none' : '';
        }
      });
    }
    // Wrap sessions in date groups
    var sessEls = Array.prototype.slice.call(list.querySelectorAll('.sess'));
    if (!sessEls.length) return;
    // Remove old headers
    var oldHdrs = list.querySelectorAll('.sess-group-hdr');
    for (var h = 0; h < oldHdrs.length; h++) oldHdrs[h].remove();
  }
  // Re-run on DOM changes
  var list = document.getElementById('sessionList');
  if (list && window.MutationObserver) {
    new MutationObserver(function () { setTimeout(group, 30); })
      .observe(list, { childList: true });
  }
  setTimeout(group, 500);
})();
})();

// ═══ Part 66: bulletproof mobile menu (event delegation, capture phase) ═══

</script>
</body>
</html>
"""
