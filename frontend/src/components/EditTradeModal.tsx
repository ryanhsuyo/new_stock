import { useState } from 'react'
import type { TradeRecord, TradeUpdateRequest } from '../types'

interface Props {
  trade: TradeRecord
  onClose: () => void
  onSave: (req: TradeUpdateRequest) => Promise<void>
}

export default function EditTradeModal({ trade, onClose, onSave }: Props) {
  const [date, setDate] = useState(trade.date)
  const [price, setPrice] = useState(String(trade.price))
  const [shares, setShares] = useState(String(trade.shares))
  const [note, setNote] = useState(trade.note)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSave({ date, price: Number(price), shares: Number(shares), note })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '修正失敗')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={event => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <div className="modal trade-edit-modal" role="dialog" aria-modal="true" aria-labelledby="trade-edit-title">
        <div className="modal-header">
          <div>
            <h2 id="trade-edit-title">修正交易紀錄</h2>
            <p>{trade.name} {trade.stock_id} · {trade.trade_type === 'buy' ? '買入' : '賣出'}</p>
          </div>
          <button className="modal-close" type="button" onClick={onClose} aria-label="關閉">×</button>
        </div>
        <form className="modal-form" onSubmit={submit}>
          <label>交易日期<input type="date" value={date} onChange={event => setDate(event.target.value)} required /></label>
          <label>成交價格<input type="number" min="0.01" step="0.01" value={price} onChange={event => setPrice(event.target.value)} required /></label>
          <label>股數<input type="number" min="1" step="1" value={shares} onChange={event => setShares(event.target.value)} required /></label>
          <label>備註<textarea value={note} onChange={event => setNote(event.target.value)} rows={3} /></label>
          <p className="trade-edit-help">股票、買賣方向保持不變；儲存前會建立備份並重新計算費稅與持倉。</p>
          {error && <p className="page-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button className="btn" type="button" onClick={onClose}>取消</button>
            <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? '儲存中…' : '確認修正'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
