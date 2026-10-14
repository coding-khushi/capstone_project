import { useState } from 'react'
import FloatingButton from './components/FloatingButton'
import ChatPanel from './components/ChatPanel'
import ProjectPanel from './components/ProjectPanel'
import './App.css'

type View = 'collapsed' | 'chat' | 'project'

export default function App() {
  const [view, setView] = useState<View>('collapsed')

  return (
    <div className="app-root">
      {view === 'collapsed' && (
        <FloatingButton onClick={() => setView('chat')} />
      )}
      {view === 'chat' && (
        <ChatPanel
          onClose={() => setView('collapsed')}
          onOpenProject={() => setView('project')}
        />
      )}
      {view === 'project' && (
        <ProjectPanel onClose={() => setView('chat')} />
      )}
    </div>
  )
}
