import { Chat, Role } from '../api';

interface Props {
  chats: Chat[];
  roles: Role[];
  activeChatId: string | null;
  activeRole: string;
  onSelectChat: (chat: Chat | null) => void;
  onSelectRole: (role: string) => void;
  onNewChat: () => void;
}

export default function Sidebar({
  chats, roles, activeChatId, activeRole,
  onSelectChat, onSelectRole, onNewChat,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <button className="btn-new" onClick={onNewChat}>+ New chat</button>
      </div>
      <div className="sidebar-section">
        <label className="sidebar-label">Role</label>
        <select value={activeRole} onChange={(e) => onSelectRole(e.target.value)} className="role-select">
          {roles.map((r) => (
            <option key={r.key} value={r.key}>{r.icon} {r.label}</option>
          ))}
        </select>
      </div>
      <div className="sidebar-section sidebar-chats">
        <label className="sidebar-label">Chats ({chats.length})</label>
        <div className="chat-list">
          {chats.length === 0 && <div className="chat-empty">No chats yet.</div>}
          {chats.map((chat) => (
            <button
              key={chat.id}
              className={`chat-item ${activeChatId === chat.sessionKey ? 'chat-item-active' : ''}`}
              onClick={() => onSelectChat(chat)}
            >
              <div className="chat-title">{chat.title || 'Untitled'}</div>
              <div className="chat-meta">{new Date(chat.updated).toLocaleDateString()}</div>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
