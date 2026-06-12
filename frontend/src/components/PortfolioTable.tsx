import type { Position } from '../types'

interface Props {
  positions: Position[]
  onSell: (position: Position) => void
}

export default function PortfolioTable({ positions, onSell }: Props) {
  if (positions.length === 0) {
    return <p className="empty-hint">目前無持倉，請先從推薦清單記錄買入。</p>
  }

  const totalCost = positions.reduce((s, p) => s + p.total_cost, 0)
  const totalValue = positions.reduce((s, p) => s + p.current_value, 0)
  const totalPnl = totalValue - totalCost
  const totalRate = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0

  return (
    <div>
      <div className="portfolio-summary">
        <div className="summary-item">
          <span className="summary-label">總成本</span>
          <span className="summary-value">{totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">收盤估值</span>
          <span className="summary-value">{totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">未實現損益</span>
          <span className={`summary-value ${totalPnl >= 0 ? 'up' : 'down'}`}>
            {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元
          </span>
        </div>
        <div className="summary-item">
          <span className="summary-label">整體報酬率</span>
          <span className={`summary-value ${totalRate >= 0 ? 'up' : 'down'}`}>
            {totalRate >= 0 ? '+' : ''}{totalRate.toFixed(2)}%
          </span>
        </div>
      </div>
      <p className="portfolio-cost-note">
        成本已含買進手續費；收盤估值與未實現損益以最新收盤價賣出後扣手續費、證交稅估算，非即時市價。
      </p>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>股票</th>
              <th>持有股數</th>
              <th>平均成本</th>
              <th>最新收盤</th>
              <th>收盤估值</th>
              <th>未實現損益</th>
              <th>報酬率</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr key={p.stock_id}>
                <td>
                  <span className="td-name">{p.name}</span>
                  <span className="td-id">{p.stock_id}</span>
                </td>
                <td>{p.total_shares.toLocaleString()}</td>
                <td>{p.avg_cost.toFixed(2)}</td>
                <td>{p.current_price.toFixed(2)}</td>
                <td>{p.current_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                <td className={p.unrealized_pnl >= 0 ? 'up' : 'down'}>
                  {p.unrealized_pnl >= 0 ? '+' : ''}{p.unrealized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </td>
                <td className={p.return_rate >= 0 ? 'up' : 'down'}>
                  {p.return_rate >= 0 ? '+' : ''}{p.return_rate.toFixed(2)}%
                </td>
                <td>
                  <button className="btn btn-sm btn-danger" onClick={() => onSell(p)}>
                    記錄賣出
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
