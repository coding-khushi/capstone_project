import { useEffect, useState } from 'react'
import FloatingButton from './components/FloatingButton'
import ChatPanel from './components/ChatPanel'
import ProjectPanel from './components/ProjectPanel'
import './App.css'

type View = 'collapsed' | 'chat' | 'project'

export default function App() {
  const [view, setView] = useState<View>('collapsed')

  // Shrink the window to the button when collapsed so it doesn't block clicks
  // on the apps behind it; grow it back when the chat or project panel opens.
  useEffect(() => {
    window.percept?.setCollapsed(view === 'collapsed')
  }, [view])

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
