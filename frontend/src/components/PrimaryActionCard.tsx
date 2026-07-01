import type { PmWorklistItem } from '../types'

interface PrimaryActionCardProps {
  primaryAction: PmWorklistItem | null
  statusClass: string
  copied: boolean
  busy: boolean
  onRunPrimaryAction: () => void
}

export default function PrimaryActionCard({
  primaryAction,
  statusClass,
  copied,
  busy,
  onRunPrimaryAction,
}: PrimaryActionCardProps) {
  const payload = primaryAction?.action_payload
  const previewItems = payload?.preview_items?.slice(0, 4) ?? []
  const expectedOutputs = payload?.expected_outputs?.slice(0, 4) ?? []
  const hasPayloadPreview = Boolean(payload?.file_path || previewItems.length > 0 || expectedOutputs.length > 0)

  return (
    <div className={`decision-console-card primary ${primaryAction?.severity ?? statusClass}`}>
      <span>現在最該做</span>
      <strong>{primaryAction?.title ?? '目前沒有 PM 優先待辦'}</strong>
      <p>{primaryAction?.detail ?? '資料流、復盤與基本面工作目前沒有阻塞項目。'}</p>
      {hasPayloadPreview && (
        <div className="primary-action-payload">
          {payload?.file_path && <code>{payload.file_path}</code>}
          {previewItems.length > 0 && (
            <div className="primary-action-preview" aria-label="主要行動預覽">
              {previewItems.map(item => <span key={item}>{item}</span>)}
            </div>
          )}
          {expectedOutputs.length > 0 && (
            <ul className="workflow-outputs">
              {expectedOutputs.map(output => <li key={output}>{output}</li>)}
            </ul>
          )}
        </div>
      )}
      {primaryAction && (
        <button className="btn btn-secondary btn-sm" onClick={onRunPrimaryAction} disabled={busy}>
          {copied ? '已複製' : primaryAction.action_label || '處理'}
        </button>
      )}
    </div>
  )
}
