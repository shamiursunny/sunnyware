import { useState, useRef, useEffect } from 'react';
import { getToken, redirectToLogin, saveAdminKey } from './auth';

interface Message { role: 'user' | 'assistant'; content: string; }

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [token, setToken] = useState<string>('');
  const [adminKey, setAdminKey] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = getToken();
    setToken(t);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleAdminSubmit = () => {
    if (!adminKey.trim()) return;
    saveAdminKey(adminKey.trim());
    setToken(adminKey.trim());
  };

  const sendMessage = async () => {
    if (!input.trim() || !token || isLoading) return;

    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/agent/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': token
        },
        body: JSON.stringify({ input: userMsg, session_id: 'react-web' })
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      console.log("DEBUG API RESPONSE:", data);

      // Robust answer extraction
      let answer = "No response";
      if (typeof data === 'string') answer = data;
      else if (data.answer) answer = data.answer;
      else if (data.response) answer = data.response;
      else if (data.text) answer = data.text;
      else if (data.result && typeof data.result === 'string') answer = data.result;
      else if (data.result && data.result.answer) answer = data.result.answer;
      else answer = JSON.stringify(data); // Fallback: show raw JSON

      setMessages(prev => [...prev, { role: 'assistant', content: answer }]);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', padding: '20px' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '10px' }}>Welcome to Sunnyware</h1>
        <p style={{ color: '#94a3b8', marginBottom: '30px' }}>Sign in to access your private workspace.</p>

        <button 
          className="login-btn" 
          onClick={redirectToLogin}
          style={{ width: '100%', maxWidth: '400px', marginBottom: '20px' }}
        >
          Sign in with Google
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '10px 0', color: '#64748b' }}>
          <div style={{ flex: 1, height: '1px', background: '#334155' }}></div>
          <span>or use admin key</span>
          <div style={{ flex: 1, height: '1px', background: '#334155' }}></div>
        </div>

        <input
          type="text"
          value={adminKey}
          onChange={e => setAdminKey(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdminSubmit()}
          placeholder="master-admin-key"
          style={{
            width: '100%', maxWidth: '400px', padding: '15px', borderRadius: '8px',
            border: '1px solid #334155', background: '#0f172a', color: 'white',
            marginBottom: '15px', fontSize: '1rem'
          }}
        />
        <button
          className="login-btn"
          onClick={handleAdminSubmit}
          disabled={!adminKey.trim()}
          style={{ width: '100%', maxWidth: '400px', background: '#7c3aed' }}
        >
          Continue
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="chat-container" ref={scrollRef}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>
            <p>Start a new chat. Ask me anything!</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.content}
          </div>
        ))}
        {isLoading && <div className="message assistant">Thinking...</div>}
      </div>
      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="Type a message..."
          disabled={isLoading}
        />
        <button onClick={sendMessage} disabled={isLoading}>Send</button>
      </div>
    </>
  );
}
