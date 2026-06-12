import type { SignalsSummary } from '../types'

const SIGNAL_LABEL: Record<string, string> = {
  entry_confirmed:     '進場確認',
  ready_to_enter:      '準備進場',
  watchlist:           '觀察中',
  hold:                '持股續抱',
  take_profit_warning: '停利觀察',
  exit_warning:        '出場警示',
  invalidated:         '多頭失效',
  DATA_MISSING:        '資料不足',
}

// 顯示順序：由積極到保守
const SIGNAL_ORDER = [
  'entry_confirmed', 'ready_to_enter', 'watchlist', 'hold',
  'take_profit_warning', 'exit_warning', 'invalidated', 'DATA_MISSING',
]

interface Props {
  summary: SignalsSummary
}

export default function NoSignalExplainer({ summary }: Props) {
  const nonZeroSignals = SIGNAL_ORDER
    .filter(k => (summary.signal_counts[k] ?? 0) > 0)
    .map(k => ({ key: k, count: summary.signal_counts[k] }))

  const topReasons = Object.entries(summary.no_buy_reason_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)

  return (
    <div className="no-signal-explainer">
      <div className="no-signal-header">
        目前無買入訊號
        <span className="no-signal-meta">
          （已分析 {summary.universe_size} 支，資料完整 {summary.data_ok_count} 支，基準日：{summary.as_of}）
        </span>
      </div>

      {nonZeroSignals.length > 0 && (
        <div className="no-signal-block">
          <div className="no-signal-block-title">訊號分布</div>
          <div className="no-signal-chips">
            {nonZeroSignals.map(({ key, count }) => (
              <span key={key} className="no-signal-chip">
                {SIGNAL_LABEL[key] ?? key}
                <span className="no-signal-chip-count">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {topReasons.length > 0 && (
        <div className="no-signal-block">
          <div className="no-signal-block-title">主要未進場原因</div>
          <ul className="no-signal-reasons">
            {topReasons.map(([reason, count]) => (
              <li key={reason}>
                {reason}
                {count > 1 && <span className="no-signal-reason-count">×{count}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
