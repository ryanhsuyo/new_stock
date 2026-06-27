import type { DailyBrief, DailyBriefStock, DailyBriefTask, ManualWatchlistReview, ManualWatchlistReviewItem } from '../types'

export const BRIEF_BUCKETS: Array<{
  key: keyof DailyBrief['rotation_plan']
  countKey: string
  label: string
  cls: string
}> = [
  { key: 'priority_reduce', countKey: 'priority_reduce_count', label: '優先減碼', cls: 'brief-risk' },
  { key: 'entry_candidates', countKey: 'entry_candidates_count', label: '可進場', cls: 'brief-enter' },
  { key: 'continue_hold', countKey: 'continue_hold_count', label: '續抱', cls: 'brief-hold' },
  { key: 'wait_pullback', countKey: 'wait_pullback_count', label: '等回測', cls: 'brief-watch' },
  { key: 'avoid_no_chase', countKey: 'avoid_no_chase_count', label: '暫不碰', cls: 'brief-muted' },
]

const TASK_BUCKET_LABEL: Record<string, string> = {
  priority_reduce: '優先減碼',
  entry_candidates: '可進場',
  continue_hold: '續抱',
  wait_pullback: '等回測',
  avoid_no_chase: '暫不碰',
  long_watch: '長期觀察',
  unassigned_watch: '觀察',
}

const MANUAL_REVIEW_SUMMARY_KEYS: Array<{ key: string; label: string }> = [
  { key: 'entry_candidates_count', label: '可小試' },
  { key: 'continue_hold_count', label: '續抱' },
  { key: 'wait_pullback_count', label: '等回測' },
  { key: 'avoid_no_chase_count', label: '先觀察' },
  { key: 'missing_count', label: '缺資料' },
]

export function BriefStockList({
  stocks,
  onAnalysis,
}: {
  stocks: DailyBriefStock[]
  onAnalysis?: (code: string) => void
}) {
  if (!stocks.length) return <span className="brief-empty">—</span>
  return (
    <div className="brief-stock-list">
      {stocks.slice(0, 4).map(stock => (
        <button
          type="button"
          className="brief-stock-token"
          key={stock.code}
          onClick={() => onAnalysis?.(stock.code)}
          disabled={!onAnalysis}
          title={onAnalysis ? '查看技術分析與線圖' : undefined}
        >
          <strong>{stock.name}</strong>
          <em>{stock.code}</em>
        </button>
      ))}
      {stocks.length > 4 && <span className="brief-more">+{stocks.length - 4}</span>}
    </div>
  )
}

export function TomorrowTaskList({
  tasks,
  onAnalysis,
}: {
  tasks: DailyBriefTask[]
  onAnalysis?: (code: string) => void
}) {
  const topTasks = tasks.slice(0, 6)
  if (!topTasks.length) {
    return <p className="empty-hint">尚無明日任務，請先重新產生訊號。</p>
  }
  return (
    <div className="brief-task-list">
      {topTasks.map(task => (
        <button
          type="button"
          className={`brief-task${onAnalysis ? ' brief-task-clickable' : ''}`}
          key={`${task.bucket}-${task.code}`}
          onClick={() => onAnalysis?.(task.code)}
          disabled={!onAnalysis}
          title={onAnalysis ? '查看技術分析與線圖' : undefined}
        >
          <div className="brief-task-main">
            <span className={`brief-badge ${task.bucket}`}>{TASK_BUCKET_LABEL[task.bucket] ?? task.bucket}</span>
            <strong>{task.name} <em>{task.code}</em></strong>
            <p>{task.reason || task.trigger_action}</p>
          </div>
          <div className="brief-task-plan">
            <span>觀察：{task.watch_price || '—'}</span>
            <span>進場：{task.entry_plan || '—'}</span>
            <span>失效：{task.invalidation || task.stop_plan || '—'}</span>
          </div>
        </button>
      ))}
    </div>
  )
}

function ManualReviewStockCard({
  item,
  onAnalysis,
}: {
  item: ManualWatchlistReviewItem
  onAnalysis?: (code: string) => void
}) {
  const clickable = Boolean(onAnalysis && item.found)
  return (
    <button
      type="button"
      className={`manual-review-item ${item.bucket}${item.found ? '' : ' missing'}`}
      onClick={() => clickable && onAnalysis?.(item.code)}
      disabled={!clickable}
      title={clickable ? '查看技術分析與線圖' : undefined}
    >
      <div className="manual-review-main">
        <span className={`brief-badge ${item.bucket}`}>{TASK_BUCKET_LABEL[item.bucket] ?? item.decision_hint ?? item.bucket}</span>
        <strong>{item.name || item.code} <em>{item.code}</em></strong>
        <p>{item.reason || item.decision_hint || '依人工盤後筆記列入觀察'}</p>
      </div>
      <div className="manual-review-plan">
        <span>觀察：{item.watch_price || item.daily_key_price || '—'}</span>
        <span>進場：{item.entry_plan || item.price_plan_note || '—'}</span>
        <span>失效：{item.invalidation || item.daily_invalidation || item.stop_plan || '—'}</span>
      </div>
    </button>
  )
}

export function ManualWatchlistReviewPanel({
  review,
  onAnalysis,
}: {
  review: ManualWatchlistReview | null
  onAnalysis?: (code: string) => void
}) {
  if (!review?.items?.length) return null

  const playbook = review.manual_playbook
  const visibleItems = review.items.slice(0, 9)
  const focusSectors = playbook?.focus_sectors?.slice(0, 4) ?? []

  return (
    <div className="manual-review-panel">
      <div className="manual-review-head">
        <div>
          <span className="old-wang-market-label">盤後觀察股校正</span>
          <strong>{review.manual_note_title || '依人工盤後筆記校正觀察清單'}</strong>
          <em>
            資料日 {review.as_of ?? '—'}
            {playbook?.target_level ? ` · 水位 ${playbook.target_level}` : ''}
            {playbook?.target_position_pct != null ? ` · 約 ${playbook.target_position_pct}%` : ''}
          </em>
        </div>
        {focusSectors.length > 0 && (
          <div className="manual-review-sectors">
            {focusSectors.map(sector => <span key={sector}>{sector}</span>)}
          </div>
        )}
      </div>
      <div className="manual-review-summary">
        {MANUAL_REVIEW_SUMMARY_KEYS.map(item => (
          <span key={item.key}>
            {item.label}
            <strong>{review.summary?.[item.key] ?? 0}</strong>
          </span>
        ))}
      </div>
      <div className="manual-review-grid">
        {visibleItems.map(item => (
          <ManualReviewStockCard key={`${item.bucket}-${item.code}`} item={item} onAnalysis={onAnalysis} />
        ))}
      </div>
      {review.items.length > visibleItems.length && (
        <div className="manual-review-more">尚有 {review.items.length - visibleItems.length} 檔可在詳細報表查看</div>
      )}
    </div>
  )
}
