import { useState, useEffect, useCallback } from 'react';
import { getToken } from './auth';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import Library from './components/Library';
import TwoFactorModal from './components/TwoFactorModal';
import {
  Role, Chat, LibraryFile, Message,
  fetchRoles, fetchChats, fetchLibrary, fetchMessages,
  TwoFactorRequiredError,
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
  const [needs2FA, setNeeds2FA] = useState(false);
  const [twoFAUser, setTwoFAUser] = useState('admin');

  useEffect(() => {
    const t = getToken();
    setToken(t);
  }, []);

  const loadData = useCallback(async (tok: string) => {
    try {
      const [rolesData, chatsData, libraryData] = await Promise.all([
        fetchRoles(tok),
        fetchChats(tok),
        fetchLibrary(tok),
      ]);
      setRoles(rolesData);
      setChats(chatsData);
      setLibrary(libraryData);
      if (rolesData.length > 0) setActiveRole(rolesData[0].key);
      setNeeds2FA(false);
    } catch (e: any) {
      if (e instanceof TwoFactorRequiredError) {
        setTwoFAUser(e.user);
        setNeeds2FA(true);
      } else {
        console.error('Failed to load initial data:', e);
      }
    }
  }, []);

  useEffect(() => {
    if (token) loadData(token);
  }, [token, loadData]);

  const handleSelectChat = async (chat: Chat | null) => {
    if (chat) {
      setActiveChatId(chat.sessionKey);
      setActiveSessionId(chat.sessionKey);
      if (chat.role) setActiveRole(chat.role);
      setLoading(true);
      try {
        const msgs = await fetchMessages(token, chat.sessionKey);
        setMessages(msgs);
      } catch (e: any) {
        if (e instanceof TwoFactorRequiredError) {
          setTwoFAUser(e.user);
          setNeeds2FA(true);
        } else {
          setMessages([]);
        }
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
    } catch (e: any) {
      if (e instanceof TwoFactorRequiredError) {
        setTwoFAUser(e.user);
        setNeeds2FA(true);
      }
    }
  };

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  if (needs2FA) {
    return (
      <TwoFactorModal
        user={twoFAUser}
        token={token}
        onSuccess={() => loadData(token)}
      />
    );
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
