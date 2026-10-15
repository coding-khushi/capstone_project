import { useState } from 'react'
import './ProjectPanel.css'

interface Props {
  onClose: () => void
}

interface IndexStats {
  files_indexed: number
  symbols_found: number
  embeddings: number
}

export default function ProjectPanel({ onClose }: Props) {
  const [folderPath, setFolderPath] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'indexing' | 'done' | 'error'>('idle')
  const [stats, setStats] = useState<IndexStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSelectFolder() {
    const result = await window.percept.selectFolder()
    if (result.path) setFolderPath(result.path)
  }

  async function handleIndex() {
    if (!folderPath) return
    setStatus('indexing')
    setError(null)
    setStats(null)

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/index?project_path=${encodeURIComponent(folderPath)}`,
        { method: 'POST' }
      )
      if (!response.ok) {
        const err = await response.text()
        throw new Error(err)
      }
      const data = await response.json()
      setStats({ files_indexed: data.files_indexed, symbols_found: data.symbols_found, embeddings: data.embeddings ?? 0 })
      setStatus('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  return (
    <div className="project-panel">
      <div className="project-header">
        <div className="project-header-left">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="3" width="12" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M1 6h12" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M4 1v2M10 1v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          <span>Index Project</span>
        </div>
        <button className="project-close" onClick={onClose}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      <div className="project-body">
        <p className="project-desc">
          Select a project folder so Percept can search and understand your codebase.
        </p>

        <button className="folder-btn" onClick={handleSelectFolder}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 4a1 1 0 011-1h3l1.5 1.5H12a1 1 0 011 1V11a1 1 0 01-1 1H2a1 1 0 01-1-1V4z" stroke="currentColor" strokeWidth="1.3"/>
          </svg>
          Browse…
        </button>

        <input
          className="folder-input"
          type="text"
          placeholder="Or paste a path, e.g. /Users/you/myproject"
          value={folderPath ?? ''}
          onChange={e => setFolderPath(e.target.value || null)}
          spellCheck={false}
        />

        {folderPath && (
          <p className="folder-path">{folderPath}</p>
        )}

        {folderPath && status !== 'indexing' && (
          <button className="index-btn" onClick={handleIndex}>
            {status === 'done' ? 'Re-index' : 'Index Project'}
          </button>
        )}

        {status === 'indexing' && (
          <div className="indexing-indicator">
            <span className="indexing-dot" />
            Indexing files…
          </div>
        )}

        {status === 'done' && stats && (
          <div className="index-stats">
            <div className="stat"><span>{stats.files_indexed}</span> files</div>
            <div className="stat"><span>{stats.symbols_found}</span> symbols</div>
            <div className="stat"><span>{stats.embeddings}</span> embeddings</div>
          </div>
        )}

        {status === 'error' && (
          <p className="index-error">{error}</p>
        )}
      </div>
    </div>
  )
}
