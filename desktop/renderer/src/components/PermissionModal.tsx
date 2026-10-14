import './PermissionModal.css'

interface Props {
  files: string[]
  onApprove: (files: string[]) => void
  onDeny: () => void
}

export default function PermissionModal({ files, onApprove, onDeny }: Props) {
  return (
    <div className="permission-overlay">
      <div className="permission-modal">
        <div className="permission-header">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="4" y="8" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M6 8V5.5a3 3 0 016 0V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="9" cy="12" r="1" fill="currentColor"/>
          </svg>
          <span>File Access Request</span>
        </div>

        <p className="permission-desc">
          Percept needs to read {files.length === 1 ? 'this file' : 'these files'} to answer your question:
        </p>

        <ul className="permission-files">
          {files.map(f => (
            <li key={f}>
              <code>{f.length > 48 ? '…' + f.slice(-48) : f}</code>
            </li>
          ))}
        </ul>

        <p className="permission-note">
          This is a one-time permission. You'll be asked again if this file is needed later.
        </p>

        <div className="permission-actions">
          <button className="deny-btn" onClick={onDeny}>Deny</button>
          <button className="approve-btn" onClick={() => onApprove(files)}>Allow Once</button>
        </div>
      </div>
    </div>
  )
}
