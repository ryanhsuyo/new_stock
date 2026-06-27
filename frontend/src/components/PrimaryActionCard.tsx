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
  return (
    <div className={`decision-console-card primary ${primaryAction?.severity ?? statusClass}`}>
      <span>現在最該做</span>
      <strong>{primaryAction?.title ?? '目前沒有 PM 優先待辦'}</strong>
      <p>{primaryAction?.detail ?? '資料流、復盤與基本面工作目前沒有阻塞項目。'}</p>
      {primaryAction && (
        <button className="btn btn-secondary btn-sm" onClick={onRunPrimaryAction} disabled={busy}>
          {copied ? '已複製' : primaryAction.action_label || '處理'}
        </button>
      )}
    </div>
  )
}
