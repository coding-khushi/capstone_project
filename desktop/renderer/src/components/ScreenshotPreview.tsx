import './ScreenshotPreview.css'

interface Props {
  dataURL: string
  onRemove: () => void
}

export default function ScreenshotPreview({ dataURL, onRemove }: Props) {
  return (
    <div className="screenshot-preview">
      <img src={dataURL} alt="Pending screenshot" className="preview-img" />
      <button className="preview-remove" onClick={onRemove} title="Remove screenshot">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      <span className="preview-label">Screenshot ready</span>
    </div>
  )
}
