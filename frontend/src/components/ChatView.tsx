import { useState, useRef, useEffect } from 'react';
import { Message, sendMessage } from '../api';

interface Props {
  token: string;
  sessionId: string;
  activeRole: string;
  messages: Message[];
  onMessagesUpdate: (msgs: Message[]) => void;
  onChatUpdated: () => void;
}

export default function ChatView({
  token, sessionId, activeRole, messages, onMessagesUpdate, onChatUpdated,
}: Props) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg = input.trim();
    const nextMsgs = [...messages, { role: 'user' as const, content: userMsg }];
    onMessagesUpdate(nextMsgs);
    setInput('');
    setIsLoading(true);
    try {
      const { answer } = await sendMessage(token, userMsg, sessionId, activeRole);
      onMessagesUpdate([...nextMsgs, { role: 'assistant' as const, content: answer }]);
      onChatUpdated();
    } catch (e: any) {
      onMessagesUpdate([...nextMsgs, { role: 'assistant' as const, content: `Error: ${e.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty-state"><p>Start a new chat. Ask me anything!</p></div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>{m.content}</div>
        ))}
        {isLoading && <div className="message message-assistant">Thinking...</div>}
      </div>
      <div className="chat-input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message..."
          disabled={isLoading}
        />
        <button onClick={handleSend} disabled={isLoading}>Send</button>
      </div>
    </div>
  );
}
