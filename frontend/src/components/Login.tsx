import { useState } from 'react';
import { redirectToLogin, saveAdminKey } from '../auth';

interface Props { onLogin: (token: string) => void; }

export default function Login({ onLogin }: Props) {
  const [adminKey, setAdminKey] = useState('');
  const handleSubmit = () => {
    if (!adminKey.trim()) return;
    saveAdminKey(adminKey.trim());
    onLogin(adminKey.trim());
  };
  return (
    <div className="login-container">
      <h1>Welcome to Sunnyware</h1>
      <p>Sign in to access your private workspace.</p>
      <button className="login-btn" onClick={redirectToLogin}>Sign in with Google</button>
      <div className="divider">
        <div className="divider-line" />
        <span>or use admin key</span>
        <div className="divider-line" />
      </div>
      <input
        type="text"
        value={adminKey}
        onChange={(e) => setAdminKey(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        placeholder="master-admin-key"
        className="login-input"
      />
      <button className="login-btn login-btn-secondary" onClick={handleSubmit} disabled={!adminKey.trim()}>
        Continue
      </button>
    </div>
  );
}
