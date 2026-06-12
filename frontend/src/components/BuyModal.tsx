import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { BuyRequest, StockRecommendation, TradingSettings } from '../types'
import { DEFAULT_TRADING_SETTINGS, estimateTradeAmounts } from '../utils/tradingFees'

type BuyModalStock = Pick<StockRecommendation, 'stock_id' | 'name' | 'price'>

interface Props {
  /** 從推薦清單點擊時傳入；null 表示手動輸入 */
  stock: BuyModalStock | null
  defaultDate?: string
  defaultNote?: string
  onClose: () => void
  onSubmit: (req: BuyRequest) => Promise<void>
}

const today = () => new Date().toISOString().slice(0, 10)

function estimateBuy(price: string, shares: string, settings: TradingSettings) {
  const priceNum = parseFloat(price)
  const sharesNum = parseInt(shares)
  if (isNaN(priceNum) || isNaN(sharesNum) || priceNum <= 0 || sharesNum <= 0) return null
  return estimateTradeAmounts('buy', priceNum, sharesNum, settings)
}

function fmtMoney(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function BuyModal({ stock, defaultDate, defaultNote = '', onClose, onSubmit }: Props) {
  const [stockId, setStockId] = useState(stock?.stock_id ?? '')
  const [name, setName] = useState(stock?.name ?? '')
  const [date, setDate] = useState(defaultDate ?? today())
  const [price, setPrice] = useState(stock ? String(stock.price) : '')
  const [shares, setShares] = useState('')
  const [note, setNote] = useState(defaultNote)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [settings, setSettings] = useState<TradingSettings>(DEFAULT_TRADING_SETTINGS)
  const estimate = estimateBuy(price, shares, settings)

  useEffect(() => {
    api.getTradingSettings().then(setSettings).catch(() => undefined)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const priceNum = parseFloat(price)
    const sharesNum = parseInt(shares)
    if (!stockId.trim() || !name.trim()) return setError('請填寫股票代號與名稱')
    if (isNaN(priceNum) || priceNum <= 0) return setError('買入價格必須大於 0')
    if (isNaN(sharesNum) || sharesNum <= 0) return setError('買入股數必須大於 0')

    setLoading(true)
    try {
      await onSubmit({ stock_id: stockId.trim().toUpperCase(), name: name.trim(), date, price: priceNum, shares: sharesNum, note })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '發生錯誤')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>記錄買入{stock ? `：${stock.name}（${stock.stock_id}）` : ''}</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {!stock && (
            <div className="form-row-2">
              <div className="form-group">
                <label>股票代號</label>
                <input value={stockId} onChange={e => setStockId(e.target.value)} placeholder="例：2330" />
              </div>
              <div className="form-group">
                <label>股票名稱</label>
                <input value={name} onChange={e => setName(e.target.value)} placeholder="例：台積電" />
              </div>
            </div>
          )}

          <div className="form-row-2">
            <div className="form-group">
              <label>買入日期</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label>買入價格（元）</label>
              <input type="number" step="0.01" min="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" />
              {stock && <small className="form-hint">已用最新收盤價預填；請改成你的真實成交價。</small>}
            </div>
          </div>

          <div className="form-group">
            <label>買入股數（股）</label>
            <input type="number" step="1" min="1" value={shares} onChange={e => setShares(e.target.value)} placeholder="1000" />
          </div>

          {estimate && (
            <div className="trade-estimate">
              <span>成交 {fmtMoney(estimate.gross)}</span>
              <span>手續費 {fmtMoney(estimate.fee)}</span>
              <strong>預估實付 {fmtMoney(estimate.net)} 元</strong>
            </div>
          )}

          <div className="form-group">
            <label>備註（選填）</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="自由填寫" />
          </div>

          {error && <p className="form-error">{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? '儲存中...' : '確認買入'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
