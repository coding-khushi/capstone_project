import { useState } from 'react'
import FloatingButton from './components/FloatingButton'
import ChatPanel from './components/ChatPanel'
import './App.css'

export default function App() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="app-root">
      {isOpen ? (
        <ChatPanel onClose={() => setIsOpen(false)} />
      ) : (
        <FloatingButton onClick={() => setIsOpen(true)} />
      )}
    </div>
  )
}
