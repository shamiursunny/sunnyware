import { useState, useEffect } from 'react';
import { getToken } from './auth';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import Library from './components/Library';
import {
  Role, Chat, LibraryFile, Message,
  fetchRoles, fetchChats, fetchLibrary, fetchMessages,
} from './api';

export default function App() {
  const [token, setToken] = useState<string>('');
  const [view, setView] = useState<'chat' | 'library'>('chat');
  const [roles, setRoles] = useState<Role[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [library, setLibrary] = useState<LibraryFile[]>([]);
  const [activeRole, setActiveRole] = useState<string>('general');
  const [activeSessionId, setActiveSessionId] = useState<string>('react-web');
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = getToken();
    setToken(t);
  }, []);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const [rolesData, chatsData, libraryData] = await Promise.all([
          fetchRoles(token),
          fetchChats(token),
          fetchLibrary(token),
        ]);
        setRoles(rolesData);
        setChats(chatsData);
        setLibrary(libraryData);
        if (rolesData.length > 0) setActiveRole(rolesData[0].key);
      } catch (e) {
        console.error('Failed to load initial data:', e);
      }
    })();
  }, [token]);

  const handleSelectChat = async (chat: Chat | null) => {
    if (chat) {
      setActiveChatId(chat.sessionKey);
      setActiveSessionId(chat.sessionKey);
      if (chat.role) setActiveRole(chat.role);
      setLoading(true);
      try {
        const msgs = await fetchMessages(token, chat.sessionKey);
        setMessages(msgs);
      } catch {
        setMessages([]);
      } finally {
        setLoading(false);
      }
    } else {
      handleNewChat();
    }
    setView('chat');
  };

  const handleNewChat = () => {
    const newId = `sunny-${Date.now().toString(36)}`;
    setActiveChatId(null);
    setActiveSessionId(newId);
    setMessages([]);
    setView('chat');
  };

  const refreshChats = async () => {
    try {
      const chatsData = await fetchChats(token);
      setChats(chatsData);
    } catch {}
  };

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return (
    <div className="app-layout">
      <Sidebar
        chats={chats}
        roles={roles}
        activeChatId={activeChatId}
        activeRole={activeRole}
        onSelectChat={handleSelectChat}
        onSelectRole={setActiveRole}
        onNewChat={handleNewChat}
      />
      <main className="app-main">
        <header className="app-header">
          <button className={`tab ${view === 'chat' ? 'tab-active' : ''}`} onClick={() => setView('chat')}>
            Chat
          </button>
          <button className={`tab ${view === 'library' ? 'tab-active' : ''}`} onClick={() => setView('library')}>
            Library ({library.length})
          </button>
        </header>
        {loading ? (
          <div className="loading">Loading...</div>
        ) : view === 'chat' ? (
          <ChatView
            token={token}
            sessionId={activeSessionId}
            activeRole={activeRole}
            messages={messages}
            onMessagesUpdate={setMessages}
            onChatUpdated={refreshChats}
          />
        ) : (
          <Library files={library} />
        )}
      </main>
    </div>
  );
}
