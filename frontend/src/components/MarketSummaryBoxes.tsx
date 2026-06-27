import type { SignalsSummary } from '../types'

const OLD_WANG_MARKET_TEXT: Record<string, string> = {
  strong: '偏多',
  caution: '觀察',
  risk: '風險',
  unknown: '未知',
}

export function OldWangMarketBox({ summary }: { summary: SignalsSummary | null }) {
  const ctx = summary?.market_context
  if (!ctx) return null
  const regime = ctx.old_wang_market_regime || 'unknown'
  const cls = regime === 'strong' ? 'strong' : regime === 'risk' ? 'risk' : 'caution'

  return (
    <div className={`old-wang-market-box ${cls}`}>
      <div>
        <span className="old-wang-market-label">老王大盤濾網</span>
        <strong>{OLD_WANG_MARKET_TEXT[regime] ?? regime}</strong>
      </div>
      <p>{ctx.old_wang_market_reason || ctx.reason || '尚無大盤濾網說明'}</p>
      <em>來源 {ctx.old_wang_market_source || ctx.benchmark_code || '—'} · {ctx.old_wang_market_filter || 'neutral'}</em>
    </div>
  )
}

export function ManualMarketNoteBox({ summary }: { summary: SignalsSummary | null }) {
  const note = summary?.manual_market_note
  if (!note) return null
  const cls = note.risk_level === 'risk' ? 'risk' : note.risk_level === 'caution' ? 'caution' : 'strong'
  const actions = note.market_actions?.slice(0, 4) ?? []
  const staleDays = note.stale_trading_days ?? 0
  const statusText = note.is_stale
    ? `舊筆記 · 距基準日 ${staleDays} 個交易日`
    : note.status_label ?? '最新筆記'

  return (
    <div className={`manual-market-note ${cls} ${note.is_stale ? 'stale' : ''}`}>
      <div className="manual-market-note-main">
        <div>
          <span className="old-wang-market-label">
            人工盤後筆記 · {note.date}
            {note.applies_to_as_of && ` / 訊號基準 ${note.applies_to_as_of}`}
          </span>
          <span className={`manual-note-status ${note.is_stale ? 'stale' : 'fresh'}`}>
            {statusText}
          </span>
          <strong>{note.title}</strong>
        </div>
        <p>{note.headline}</p>
        {note.is_stale && note.stale_reason && <p className="manual-note-warning">{note.stale_reason}</p>}
        {note.position_guidance && <em>{note.position_guidance}</em>}
      </div>
      {actions.length > 0 && (
        <ul>
          {actions.map((action, index) => <li key={index}>{action}</li>)}
        </ul>
      )}
    </div>
  )
}
