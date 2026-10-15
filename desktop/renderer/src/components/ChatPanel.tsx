import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import PermissionModal from './PermissionModal'
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
  onOpenProject: () => void
}

declare global {
  interface Window {
    percept: {
      captureScreen: () => Promise<{ success: boolean; dataURL?: string; error?: string }>
      getScreenSource: () => Promise<{ success: boolean; sourceId?: string; error?: string }>
      selectFolder: () => Promise<{ path: string | null }>
      selectFile: (hint?: string) => Promise<{ path: string | null }>
      hideWindow: () => Promise<void>
      getWindowState: () => Promise<{ isVisible: boolean }>
    }
  }
}

export default function ChatPanel({ onClose, onOpenProject }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      content: "Hi! I'm Percept. Press the record button to start watching your screen, then ask me anything.",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [showCapturedToast, setShowCapturedToast] = useState(false)

  // Pending hard permission (get_file mid-loop)
  const [pendingPermission, setPendingPermission] = useState<string[] | null>(null)
  const [pendingQuery, setPendingQuery] = useState<{ question: string; frameDataURL: string | null } | null>(null)

  // Soft file suggestion (Gemini spotted a file on screen)
  const [suggestedFiles, setSuggestedFiles] = useState<string[] | null>(null)
  const [alreadyPermitted, setAlreadyPermitted] = useState<Set<string>>(new Set())

  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Clean up stream on unmount
  useEffect(() => {
    return () => { streamRef.current?.getTracks().forEach(t => t.stop()) }
  }, [])

  async function startRecording() {
    const result = await window.percept.getScreenSource()
    if (!result.success || !result.sourceId) {
      addAssistantMessage(`Could not start recording: ${result.error ?? 'no screen source'}`)
      return
    }
    try {
      const stream = await (navigator.mediaDevices.getUserMedia as (c: object) => Promise<MediaStream>)({
        audio: false,
        video: {
          mandatory: {
            chromeMediaSource: 'desktop',
            chromeMediaSourceId: result.sourceId,
            minWidth: 1280, maxWidth: 1920,
            minHeight: 720, maxHeight: 1080,
          },
        },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setIsRecording(true)
    } catch (err) {
      addAssistantMessage(`Recording failed: ${String(err)}`)
    }
  }

  function stopRecording() {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setIsRecording(false)
  }

  function captureFrame(): string | null {
    const video = videoRef.current
    if (!video || !isRecording || video.videoWidth === 0) return null
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.85)
  }

  function addAssistantMessage(content: string) {
    setMessages(prev => [
      ...prev,
      { id: Date.now().toString(), role: 'assistant', content, timestamp: new Date() },
    ])
  }

  async function sendQuery(
    question: string,
    frameDataURL: string | null,
    permittedFiles: string[] = [],
    suppressSuggestions: Set<string> = new Set(),
  ) {
    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          screenshot_b64: frameDataURL ?? null,
          active_file: null,
          permitted_files: permittedFiles,
        }),
      })

      if (!response.ok) {
        const err = await response.text()
        throw new Error(`Backend ${response.status}: ${err}`)
      }

      const data = await response.json()

      if (data.permission_required && data.permission_required.length > 0) {
        setPendingQuery({ question, frameDataURL })
        setPendingPermission(data.permission_required)
        return
      }

      addAssistantMessage(data.answer)

      if (data.suggested_files?.length > 0) {
        // Use suppressSuggestions (passed-in fresh set) to avoid stale closure on alreadyPermitted
        const fresh = data.suggested_files.filter(
          (f: string) => !alreadyPermitted.has(f) && !suppressSuggestions.has(f)
        )
        if (fresh.length > 0) setSuggestedFiles(fresh)
      }

      if (data.sources?.length > 0) {
        addAssistantMessage(`_Sources: ${data.sources.join(', ')}_`)
      }
    } catch (err) {
      addAssistantMessage(
        `Could not reach backend: ${err instanceof Error ? err.message : String(err)}. ` +
        'Make sure the FastAPI server is running on port 8000.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || isLoading) return

    const frameDataURL = captureFrame()

    if (isRecording && frameDataURL) {
      setShowCapturedToast(true)
      setTimeout(() => setShowCapturedToast(false), 1200)
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      screenshot: frameDataURL ?? undefined,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setSuggestedFiles(null)
    setPendingQuery({ question: text, frameDataURL })

    // Pass already-permitted files so the backend injects their content on every query
    await sendQuery(text, frameDataURL, [...alreadyPermitted])
  }

  async function handlePermissionApprove(files: string[]) {
    setPendingPermission(null)
    if (!pendingQuery) return
    const { question, frameDataURL } = pendingQuery
    setPendingQuery(null)
    await sendQuery(question, frameDataURL, files)
  }

  function handlePermissionDeny() {
    setPendingPermission(null)
    setPendingQuery(null)
    addAssistantMessage("File access denied. I'll answer with what I can see on screen only.")
  }

  async function handleSuggestionAllow() {
    if (!suggestedFiles || !pendingQuery) return

    // Open a file picker so the user picks the actual file path on disk
    const hint = suggestedFiles[0]
    const result = await window.percept.selectFile(hint)
    if (!result.path) return  // user canceled — keep banner visible

    const actualPath = result.path
    const newPermitted = new Set([...alreadyPermitted, actualPath])
    setAlreadyPermitted(newPermitted)
    setSuggestedFiles(null)
    await sendQuery(pendingQuery.question, pendingQuery.frameDataURL, [actualPath], newPermitted)
  }

  function handleSuggestionDismiss() {
    setSuggestedFiles(null)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      {/* Hidden video element for screen recording */}
      <video ref={videoRef} style={{ display: 'none' }} muted />

      {/* Permission modal overlay */}
      {pendingPermission && (
        <PermissionModal
          files={pendingPermission}
          onApprove={handlePermissionApprove}
          onDeny={handlePermissionDeny}
        />
      )}

      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <div className={`percept-dot ${isRecording ? 'recording' : ''}`} />
          <span className="chat-title">Percept</span>
          <span className="chat-badge">v0.1</span>
        </div>
        <div className="header-actions">
          <button className="header-btn" onClick={onOpenProject} title="Index project">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 4a1 1 0 011-1h3l1.5 1.5H12a1 1 0 011 1V11a1 1 0 01-1 1H2a1 1 0 01-1-1V4z" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
          </button>
          <button className="close-btn" onClick={onClose} title="Minimize">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Recording status bar */}
      {isRecording && (
        <div className="recording-bar">
          <span className="rec-dot" />
          Recording your screen — ask anything
        </div>
      )}

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

      {/* Soft file suggestion banner */}
      {suggestedFiles && suggestedFiles.length > 0 && (
        <div className="suggestion-banner">
          <div className="suggestion-text">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M6.5 5.5v4M6.5 4h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
            I can answer better with access to <strong>{suggestedFiles[0].split('/').pop() ?? suggestedFiles[0]}</strong>
          </div>
          <div className="suggestion-actions">
            <button className="suggestion-dismiss" onClick={handleSuggestionDismiss}>Skip</button>
            <button className="suggestion-allow" onClick={handleSuggestionAllow}>Allow Once</button>
          </div>
        </div>
      )}

      {/* Frame captured toast */}
      {showCapturedToast && (
        <div className="captured-toast">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Frame captured
        </div>
      )}

      {/* Input area */}
      <div className="input-area">
        <button
          className={`record-btn ${isRecording ? 'active' : ''}`}
          onClick={isRecording ? stopRecording : startRecording}
          title={isRecording ? 'Stop recording' : 'Start recording'}
        >
          {isRecording ? (
            /* Stop icon */
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="2" y="2" width="10" height="10" rx="2" fill="currentColor"/>
            </svg>
          ) : (
            /* Record icon */
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="7" cy="7" r="2.5" fill="currentColor"/>
            </svg>
          )}
        </button>

        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder={isRecording ? 'Ask about your screen…' : 'Start recording first, then ask…'}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />

        <button
          className="send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
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
