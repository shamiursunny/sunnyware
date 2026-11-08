import { useState } from 'react';
import { verify2FA } from '../api';

interface Props {
  user: string;
  token: string;
  onSuccess: () => void;
}

export default function TwoFactorModal({ user, token, onSuccess }: Props) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (code.length !== 6 || loading) return;
    setLoading(true);
    setError('');
    try {
      const result = await verify2FA(token, user, code);
      if (result.ok) onSuccess();
      else setError(result.error || 'Verification failed');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <h1>Two-Factor Authentication</h1>
      <p>
        Enter the 6-digit code from your authenticator app for <strong>{user}</strong>.
      </p>
      <input
        type="text"
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        placeholder="123456"
        className="login-input"
        autoFocus
        maxLength={6}
        style={{ fontSize: 28, letterSpacing: 8, textAlign: 'center', fontFamily: 'monospace' }}
      />
      {error && (
        <p style={{ color: '#f87171', marginBottom: 16, maxWidth: 400, textAlign: 'center' }}>
          {error}
        </p>
      )}
      <button
        className="login-btn login-btn-secondary"
        onClick={handleSubmit}
        disabled={code.length !== 6 || loading}
      >
        {loading ? 'Verifying...' : 'Verify'}
      </button>
      <p style={{ color: '#94a3b8', fontSize: 13, marginTop: 12, textAlign: 'center', maxWidth: 400 }}>
        Or use a backup code. After 5 failed attempts you will be locked out for 15 minutes.
      </p>
    </div>
  );
}
