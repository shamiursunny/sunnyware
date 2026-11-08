const API_KEY_HEADER = 'X-API-Key';

export interface Role {
  key: string;
  label: string;
  icon: string;
}

export interface Chat {
  id: string;
  sessionUuid: string;
  sessionKey: string;
  title: string;
  created: string;
  updated: string;
  role: string;
}

export interface LibraryFile {
  id: string;
  name: string;
  type: string;
  size: number;
  kind: string;
  content?: string;
  created_at: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, {
    headers: { [API_KEY_HEADER]: token },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
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

export async function fetchMessages(
  token: string,
  sessionId: string
): Promise<Message[]> {
  const endpoints = [
    `/api/chats/${encodeURIComponent(sessionId)}/messages`,
    `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
    `/api/messages?session_id=${encodeURIComponent(sessionId)}`,
  ];
  for (const ep of endpoints) {
    try {
      const data = await apiGet<any>(ep, token);
      const msgs = data.messages || data.chat?.messages || [];
      if (Array.isArray(msgs) && msgs.length > 0) return msgs;
    } catch {
      continue;
    }
  }
  return [];
}

export async function sendMessage(
  token: string,
  input: string,
  sessionId: string,
  role: string
): Promise<{ answer: string; raw: any }> {
  const res = await fetch('/api/agent/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      [API_KEY_HEADER]: token,
    },
    body: JSON.stringify({
      input,
      session_id: sessionId,
      role: role || undefined,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();

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
