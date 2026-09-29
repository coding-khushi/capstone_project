import { ChatMessage } from './ChatPanel'
import './Message.css'

interface Props {
  message: ChatMessage
}

export default function Message({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      {!isUser && (
        <div className="message-avatar">P</div>
      )}
      <div className="message-body">
        {message.screenshot && (
          <img
            className="message-screenshot"
            src={message.screenshot}
            alt="Screen capture"
          />
        )}
        <div className="message-text">{message.content}</div>
        <div className="message-time">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}
