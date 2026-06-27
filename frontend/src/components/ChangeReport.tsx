import type { SignalsSummary } from '../types'

const SIGNAL_TEXT: Record<string, string> = {
  entry_confirmed: '入場確認',
  ready_to_enter: '準備入場',
  watchlist: '觀察中',
  hold: '持股中',
  take_profit_warning: '停利觀察',
  exit_warning: '出場警示',
  invalidated: '訊號失效',
  DATA_MISSING: '資料不足',
}

export default function ChangeReport({ summary }: { summary: SignalsSummary | null }) {
  const report = summary?.change_report
  if (!report) return null

  const newItems = report.new_recommendations.slice(0, 5)
  const removedItems = report.removed_recommendations.slice(0, 5)
  const changedItems = report.signal_changes.slice(0, 6)

  return (
    <div className="dash-section">
      <h3 className="dash-section-title">本次變化</h3>
      <div className="change-report">
        <div className="change-report-meta">
          {report.has_previous
            ? <>與前次資料日 <strong>{report.previous_as_of ?? '—'}</strong> 比較</>
            : '尚無前次 summary，這次先建立比較基準'}
        </div>
        <div className="change-summary-grid">
          <div><span>新增推薦</span><strong>{report.summary.new_count}</strong></div>
          <div><span>移出推薦</span><strong>{report.summary.removed_count}</strong></div>
          <div><span>狀態變化</span><strong>{report.summary.changed_count}</strong></div>
        </div>
        {(newItems.length > 0 || removedItems.length > 0 || changedItems.length > 0) && (
          <div className="change-columns">
            {newItems.length > 0 && (
              <div>
                <div className="change-title">新增推薦</div>
                {newItems.map(item => (
                  <div className="change-item" key={`new-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{SIGNAL_TEXT[item.internal_signal] ?? item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
            {removedItems.length > 0 && (
              <div>
                <div className="change-title">移出推薦</div>
                {removedItems.map(item => (
                  <div className="change-item" key={`removed-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{item.no_buy_reason || SIGNAL_TEXT[item.internal_signal] || item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
            {changedItems.length > 0 && (
              <div>
                <div className="change-title">狀態變化</div>
                {changedItems.map(item => (
                  <div className="change-item" key={`changed-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{SIGNAL_TEXT[item.previous_signal ?? ''] ?? item.previous_signal} → {SIGNAL_TEXT[item.internal_signal] ?? item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
