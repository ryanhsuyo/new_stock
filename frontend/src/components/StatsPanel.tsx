import type { Stats } from '../types'

interface Props {
  monthly: Stats | null
  all: Stats | null
  activePeriod: 'monthly' | 'all'
  onChangePeriod: (p: 'monthly' | 'all') => void
}

function PnlValue({ value }: { value: number }) {
  const cls = value > 0 ? 'up' : value < 0 ? 'down' : 'flat'
  const sign = value > 0 ? '+' : ''
  return (
    <span className={`stat-value ${cls}`}>
      {sign}{value.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元
    </span>
  )
}

export default function StatsPanel({ monthly, all, activePeriod, onChangePeriod }: Props) {
  const data = activePeriod === 'monthly' ? monthly : all

  return (
    <div>
      <div className="period-toggle">
        <button
          className={activePeriod === 'monthly' ? 'active' : ''}
          onClick={() => onChangePeriod('monthly')}
        >
          本月
        </button>
        <button
          className={activePeriod === 'all' ? 'active' : ''}
          onClick={() => onChangePeriod('all')}
        >
          全部
        </button>
      </div>

      {data ? (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">買入筆數</div>
            <div className="stat-value neutral">{data.buy_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">賣出筆數</div>
            <div className="stat-value neutral">{data.sell_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">已實現損益</div>
            <PnlValue value={data.realized_pnl} />
          </div>
          <div className="stat-card">
            <div className="stat-label">未實現損益</div>
            <PnlValue value={data.unrealized_pnl} />
          </div>
          <div className="stat-card stat-card-wide">
            <div className="stat-label">勝率（已結清交易）</div>
            <div className={`stat-value ${data.win_rate >= 50 ? 'up' : data.win_rate > 0 ? 'down' : 'flat'}`}>
              {data.sell_count > 0 ? `${data.win_rate.toFixed(1)}%` : '—'}
            </div>
            {data.sell_count === 0 && (
              <div className="stat-note">尚無賣出紀錄</div>
            )}
          </div>
        </div>
      ) : (
        <p className="empty-hint">載入中…</p>
      )}
    </div>
  )
}
