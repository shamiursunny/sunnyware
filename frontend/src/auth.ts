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
