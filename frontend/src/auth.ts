export function getToken(): string {
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get('token');
  if (urlToken) {
    localStorage.setItem('sunnyware_chat_key', urlToken);
    window.history.replaceState({}, document.title, window.location.pathname);
    return urlToken;
  }
  return localStorage.getItem('sunnyware_chat_key') || '';
}

export function saveAdminKey(key: string) {
  localStorage.setItem('sunnyware_chat_key', key);
}

export function redirectToLogin() {
  window.location.href = '/auth/google';
}

export function get2FASession(): string {
  return localStorage.getItem('sunnyware_2fa_session') || '';
}

export function save2FASession(token: string) {
  localStorage.setItem('sunnyware_2fa_session', token);
}

export function clear2FASession() {
  localStorage.removeItem('sunnyware_2fa_session');
}
