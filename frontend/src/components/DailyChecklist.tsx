import type { DailyChecklistItem } from '../types'

interface Props {
  items?: DailyChecklistItem[] | null
  compact?: boolean
}

const STATUS_LABEL: Record<string, string> = {
  pass: '通過',
  warn: '留意',
  fail: '未過',
  info: '資訊',
}

const CATEGORY_LABEL: Record<string, string> = {
  market: '大盤',
  setup: '型態',
  risk: '風險',
  action: '動作',
}

export default function DailyChecklist({ items, compact = false }: Props) {
  const visible = (items ?? []).filter(item => item && item.label && item.detail)
  if (visible.length === 0) return null

  return (
    <div className={`daily-checklist${compact ? ' compact' : ''}`}>
      {visible.map((item, idx) => (
        <div key={`${item.category}-${item.label}-${idx}`} className={`daily-check-item ${item.status}`}>
          <div className="daily-check-top">
            <span className="daily-check-category">
              {CATEGORY_LABEL[item.category] ?? item.category}
            </span>
            <span className={`daily-check-status ${item.status}`}>
              {STATUS_LABEL[item.status] ?? item.status}
            </span>
          </div>
          <strong>{item.label}</strong>
          <span>{item.detail}</span>
          {item.key_price && <em>{item.key_price}</em>}
        </div>
      ))}
    </div>
  )
}
