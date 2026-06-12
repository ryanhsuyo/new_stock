import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Position, SellRequest, TradingSettings } from '../types'
import { DEFAULT_TRADING_SETTINGS, estimateTradeAmounts } from '../utils/tradingFees'

interface Props {
  position: Position
  onClose: () => void
  onSubmit: (req: SellRequest) => Promise<void>
}

const today = () => new Date().toISOString().slice(0, 10)

function estimateSell(price: string, shares: string, avgCost: number, settings: TradingSettings) {
  const priceNum = parseFloat(price)
  const sharesNum = parseInt(shares)
  if (isNaN(priceNum) || isNaN(sharesNum) || priceNum <= 0 || sharesNum <= 0) return null
  const { gross, fee, tax, net } = estimateTradeAmounts('sell', priceNum, sharesNum, settings)
  const cost = avgCost * sharesNum
  return { gross, fee, tax, net, pnl: net - cost }
}

function fmtMoney(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function SellModal({ position, onClose, onSubmit }: Props) {
  const [date, setDate] = useState(today())
  const [price, setPrice] = useState(position.current_price > 0 ? String(position.current_price) : '')
  const [shares, setShares] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [settings, setSettings] = useState<TradingSettings>(DEFAULT_TRADING_SETTINGS)

  useEffect(() => {
    api.getTradingSettings().then(setSettings).catch(() => undefined)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const priceNum = parseFloat(price)
    const sharesNum = parseInt(shares)
    if (isNaN(priceNum) || priceNum <= 0) return setError('賣出價格必須大於 0')
    if (isNaN(sharesNum) || sharesNum <= 0) return setError('賣出股數必須大於 0')
    if (sharesNum > position.total_shares) return setError(`最多可賣出 ${position.total_shares} 股`)

    setLoading(true)
    try {
      await onSubmit({ stock_id: position.stock_id, date, price: priceNum, shares: sharesNum, note })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '發生錯誤')
    } finally {
      setLoading(false)
    }
  }

  const estimate = estimateSell(price, shares, position.avg_cost, settings)

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>記錄賣出：{position.name}（{position.stock_id}）</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="sell-position-info">
          <span>持有股數：<strong>{position.total_shares.toLocaleString()} 股</strong></span>
          <span>平均成本：<strong>{position.avg_cost.toFixed(2)} 元</strong></span>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-row-2">
            <div className="form-group">
              <label>賣出日期</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label>賣出價格（元）</label>
              <input type="number" step="0.01" min="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" />
              <small className="form-hint">已用持股最新收盤價預填；請改成你的真實成交價。</small>
            </div>
          </div>

          <div className="form-group">
            <label>賣出股數（最多 {position.total_shares.toLocaleString()} 股）</label>
            <input type="number" step="1" min="1" max={position.total_shares} value={shares} onChange={e => setShares(e.target.value)} placeholder="1000" />
          </div>

          {estimate && (
            <div className={`est-pnl ${estimate.pnl >= 0 ? 'up' : 'down'}`}>
              <span>成交 {fmtMoney(estimate.gross)} · 手續費 {fmtMoney(estimate.fee)} · 證交稅 {fmtMoney(estimate.tax)}</span>
              <strong>
                預估實收 {fmtMoney(estimate.net)} 元 / 損益 {estimate.pnl >= 0 ? '+' : ''}{fmtMoney(Math.round(estimate.pnl))} 元
              </strong>
            </div>
          )}

          <div className="form-group">
            <label>備註（選填）</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="自由填寫" />
          </div>

          {error && <p className="form-error">{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-danger" disabled={loading}>
              {loading ? '儲存中...' : '確認賣出'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
