import { get2FASession, save2FASession } from './auth';

const API_KEY_HEADER = 'X-API-Key';

export class TwoFactorRequiredError extends Error {
  user: string;
  constructor(user: string) {
    super('2FA_REQUIRED');
    this.name = 'TwoFactorRequiredError';
    this.user = user;
  }
}

export interface Role { key: string; label: string; icon: string; }
export interface Chat {
  id: string; sessionUuid: string; sessionKey: string; title: string;
  created: string; updated: string; role: string;
}
export interface LibraryFile {
  id: string; name: string; type: string; size: number;
  kind: string; content?: string; created_at: string;
}
export interface Message { role: 'user' | 'assistant'; content: string; }

function buildHeaders(token: string, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    [API_KEY_HEADER]: token,
    ...(extra || {}),
  };
  const sess = get2FASession();
  if (sess) headers['x-2fa-session'] = sess;
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 428) {
    let body: any = {};
    try { body = await res.json(); } catch {}
    throw new TwoFactorRequiredError(body.user || 'admin');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, { headers: buildHeaders(token) });
  return handleResponse<T>(res);
}

export async function fetchRoles(token: string): Promise<Role[]> {
  const data = await apiGet<{ roles: Role[] }>('/api/roles', token);
  return data.roles || [];
}

export async function fetchChats(token: string): Promise<Chat[]> {
  const data = await apiGet<{ chats: Chat[] }>('/api/chats', token);
  return data.chats || [];
}

export async function fetchLibrary(token: string): Promise<LibraryFile[]> {
  const data = await apiGet<{ files: LibraryFile[] }>('/api/library/files', token);
  return data.files || [];
}

export async function fetchMessages(token: string, sessionId: string): Promise<Message[]> {
  const endpoints = [
    `/api/chats/${encodeURIComponent(sessionId)}/messages`,
    `/api/sessions/${encodeURIComponent(sessionId)}/history?limit=200`,
  ];
  for (const ep of endpoints) {
    try {
      const data = await apiGet<any>(ep, token);
      const msgs = data.messages || data.chat?.messages || data.history || [];
      if (Array.isArray(msgs) && msgs.length > 0) return msgs;
    } catch (e: any) {
      if (e instanceof TwoFactorRequiredError) throw e;
      continue;
    }
  }
  return [];
}

export async function sendMessage(
  token: string, input: string, sessionId: string, role: string
): Promise<{ answer: string; raw: any }> {
  const res = await fetch('/api/agent/run', {
    method: 'POST',
    headers: buildHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ input, session_id: sessionId, role: role || undefined }),
  });
  const data = await handleResponse<any>(res);
  let answer = '';
  if (typeof data === 'string') answer = data;
  else if (data.result && typeof data.result === 'string') answer = data.result;
  else if (data.result?.answer) answer = data.result.answer;
  else if (data.answer) answer = data.answer;
  else if (data.response) answer = data.response;
  else if (data.text) answer = data.text;
  else answer = JSON.stringify(data);
  return { answer, raw: data };
}

export async function verify2FA(
  token: string, user: string, code: string
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch('/api/2fa/verify-login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      [API_KEY_HEADER]: token,
    },
    body: JSON.stringify({ user, code }),
  });
  let data: any = {};
  try { data = await res.json(); } catch {}
  if (!res.ok || !data.ok) {
    return { ok: false, error: data.error || `HTTP ${res.status}` };
  }
  if (data.session_token) save2FASession(data.session_token);
  return { ok: true };
}
