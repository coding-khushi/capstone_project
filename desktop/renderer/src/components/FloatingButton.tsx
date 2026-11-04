import './FloatingButton.css'

interface Props {
  onClick: () => void
}

export default function FloatingButton({ onClick }: Props) {
  return (
    <div className="floating-pill">
      {/* Drag handle — on Windows a region can't be both draggable and clickable,
          so moving the button uses this grip and the rest of the pill opens the chat. */}
      <div className="floating-grip" title="Drag to move">
        <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor">
          <circle cx="2.5" cy="3" r="1.4" />
          <circle cx="7.5" cy="3" r="1.4" />
          <circle cx="2.5" cy="8" r="1.4" />
          <circle cx="7.5" cy="8" r="1.4" />
          <circle cx="2.5" cy="13" r="1.4" />
          <circle cx="7.5" cy="13" r="1.4" />
        </svg>
      </div>
      <button className="floating-btn" onClick={onClick} title="Open Percept (Ctrl+Shift+P)">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          {/* Eye icon — Percept "sees" your screen */}
          <ellipse cx="12" cy="12" rx="10" ry="6" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
          <circle cx="13" cy="11" r="1" fill="white" opacity="0.6" />
        </svg>
        <span className="floating-btn-label">Percept</span>
      </button>
    </div>
  )
}
