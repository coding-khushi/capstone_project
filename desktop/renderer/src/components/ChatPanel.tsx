import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import ScreenshotPreview from './ScreenshotPreview'
import './ChatPanel.css'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  screenshot?: string
  timestamp: Date
}

interface Props {
  onClose: () => void
}

declare global {
  interface Window {
    percept: {
      captureScreen: () => Promise<{ success: boolean; dataURL?: string; error?: string }>
      hideWindow: () => Promise<void>
      getWindowState: () => Promise<{ isVisible: boolean }>
    }
  }
}

export default function ChatPanel({ onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      content: "Hi! I'm Percept. I can see your screen and help you understand what's happening. Press the camera button to capture your screen, then ask me anything.",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isCapturing, setIsCapturing] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [pendingScreenshot, setPendingScreenshot] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  async function handleCapture() {
    setIsCapturing(true)
    try {
      const result = await window.percept.captureScreen()
      if (result.success && result.dataURL) {
        setPendingScreenshot(result.dataURL)
      } else {
        addAssistantMessage(`Screen capture failed: ${result.error ?? 'unknown error'}`)
      }
    } finally {
      setIsCapturing(false)
    }
  }

  function addAssistantMessage(content: string) {
    setMessages(prev => [
      ...prev,
      { id: Date.now().toString(), role: 'assistant', content, timestamp: new Date() },
    ])
  }

  async function handleSend() {
    const text = input.trim()
    if (!text && !pendingScreenshot) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      screenshot: pendingScreenshot ?? undefined,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text || 'What do you see on my screen?',
          screenshot_b64: userMessage.screenshot ?? null,
          active_file: null,
        }),
      })

      if (!response.ok) {
        const err = await response.text()
        throw new Error(`Backend ${response.status}: ${err}`)
      }

      const data = await response.json()
      addAssistantMessage(data.answer)
    } catch (err) {
      addAssistantMessage(
        `Could not reach backend: ${err instanceof Error ? err.message : String(err)}. ` +
        'Make sure the FastAPI server is running on port 8000.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="percept-dot" />
          <span className="chat-title">Percept</span>
          <span className="chat-badge">v0.1</span>
        </div>
        <button className="close-btn" onClick={onClose} title="Minimize">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="messages-area">
        {messages.map(msg => (
          <Message key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="loading-dots">
            <span /><span /><span />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Screenshot preview strip */}
      {pendingScreenshot && (
        <ScreenshotPreview
          dataURL={pendingScreenshot}
          onRemove={() => setPendingScreenshot(null)}
        />
      )}

      {/* Input area */}
      <div className="input-area">
        <button
          className={`capture-btn ${isCapturing ? 'capturing' : ''}`}
          onClick={handleCapture}
          disabled={isCapturing}
          title="Capture screen"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="1" y="4" width="16" height="11" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="9" cy="9.5" r="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M6 4V3a1 1 0 011-1h4a1 1 0 011 1v1" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>

        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Ask Percept anything..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />

        <button
          className="send-btn"
          onClick={handleSend}
          disabled={(!input.trim() && !pendingScreenshot) || isLoading}
          title="Send (Enter)"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M14 8L2 2l3 6-3 6 12-6z" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>
  )
}
