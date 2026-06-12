import { useState } from 'react'
import type { BuyRequest, SellRequest } from '../types'

interface Props {
  initialType?: 'buy' | 'sell'
  onClose: () => void
  onBuy: (req: BuyRequest) => Promise<void>
  onSell: (req: SellRequest) => Promise<void>
}

const today = () => new Date().toISOString().slice(0, 10)

export default function ManualTradeModal({ initialType = 'buy', onClose, onBuy, onSell }: Props) {
  const [tradeType, setTradeType] = useState<'buy' | 'sell'>(initialType)
  const [stockId, setStockId] = useState('')
  const [name, setName] = useState('')
  const [date, setDate] = useState(today())
  const [price, setPrice] = useState('')
  const [shares, setShares] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const sid = stockId.trim().toUpperCase()
    const priceNum = parseFloat(price)
    const sharesNum = parseInt(shares)
    if (!sid) return setError('請填寫股票代號')
    if (tradeType === 'buy' && !name.trim()) return setError('買入紀錄請填寫股票名稱')
    if (isNaN(priceNum) || priceNum <= 0) return setError('價格必須大於 0')
    if (isNaN(sharesNum) || sharesNum <= 0) return setError('股數必須大於 0')

    setLoading(true)
    try {
      if (tradeType === 'buy') {
        await onBuy({
          stock_id: sid,
          name: name.trim(),
          date,
          price: priceNum,
          shares: sharesNum,
          note,
        })
      } else {
        await onSell({
          stock_id: sid,
          date,
          price: priceNum,
          shares: sharesNum,
          note,
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '儲存失敗')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{tradeType === 'buy' ? '手動記錄買入' : '手動記錄賣出'}</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="trade-type-toggle" role="group" aria-label="交易類型">
            <button
              type="button"
              className={`trade-type-option ${tradeType === 'buy' ? 'active' : ''}`}
              onClick={() => { setTradeType('buy'); setError('') }}
            >
              買入
            </button>
            <button
              type="button"
              className={`trade-type-option ${tradeType === 'sell' ? 'active' : ''}`}
              onClick={() => { setTradeType('sell'); setError('') }}
            >
              賣出
            </button>
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label>股票代號</label>
              <input value={stockId} onChange={e => setStockId(e.target.value)} placeholder="例：2330" />
            </div>
            <div className="form-group">
              <label>股票名稱{tradeType === 'sell' ? '（賣出可免填）' : ''}</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder={tradeType === 'sell' ? '由既有持股帶入' : '例：台積電'}
                disabled={tradeType === 'sell'}
              />
            </div>
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label>{tradeType === 'buy' ? '買入日期' : '賣出日期'}</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label>{tradeType === 'buy' ? '買入價格（元）' : '賣出價格（元）'}</label>
              <input type="number" step="0.01" min="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" />
            </div>
          </div>

          <div className="form-group">
            <label>{tradeType === 'buy' ? '買入股數（股）' : '賣出股數（股）'}</label>
            <input type="number" step="1" min="1" value={shares} onChange={e => setShares(e.target.value)} placeholder="1000" />
          </div>

          <div className="form-group">
            <label>備註（選填）</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="自由填寫" />
          </div>

          {error && <p className="form-error">{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
            <button type="submit" className={tradeType === 'buy' ? 'btn btn-primary' : 'btn btn-danger'} disabled={loading}>
              {loading ? '儲存中...' : tradeType === 'buy' ? '確認買入' : '確認賣出'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
