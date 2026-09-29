import './FloatingButton.css'

interface Props {
  onClick: () => void
}

export default function FloatingButton({ onClick }: Props) {
  return (
    <button className="floating-btn" onClick={onClick} title="Open Percept (Ctrl+Shift+P)">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        {/* Eye icon — Percept "sees" your screen */}
        <ellipse cx="12" cy="12" rx="10" ry="6" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="12" cy="12" r="3" fill="currentColor" />
        <circle cx="13" cy="11" r="1" fill="white" opacity="0.6" />
      </svg>
      <span className="floating-btn-label">Percept</span>
    </button>
  )
}
