import { useEffect, useState } from 'react'
import { api } from '../api/client'
import ManualTradeModal from '../components/ManualTradeModal'
import TradeTable from '../components/TradeTable'
import type { BuyRequest, SellRequest, TradeRecord } from '../types'

export default function TradesPage() {
  const [trades, setTrades] = useState<TradeRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [msg, setMsg] = useState('')

  const refreshTrades = () =>
    api.getTrades()
      .then(setTrades)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

  useEffect(() => {
    refreshTrades()
  }, [])

  const handleBuy = async (req: BuyRequest) => {
    await api.buyStock(req)
    setMsg(`已記錄買入：${req.name}（${req.stock_id}）`)
    await refreshTrades()
  }

  const handleSell = async (req: SellRequest) => {
    await api.sellStock(req)
    setMsg(`已記錄賣出：${req.stock_id}`)
    await refreshTrades()
  }

  if (loading) return <p className="page-loading">載入中…</p>
  if (error) return <p className="page-error">{error}</p>

  return (
    <div>
      <div className="page-actions">
        <h2 className="page-subtitle">交易紀錄（共 {trades.length} 筆）</h2>
        <button className="btn btn-primary" onClick={() => { setMsg(''); setModalOpen(true) }}>
          + 新增交易
        </button>
      </div>
      {msg && <div className="run-msg trade-page-msg">{msg}</div>}
      <TradeTable trades={trades} />
      {modalOpen && (
        <ManualTradeModal
          onClose={() => setModalOpen(false)}
          onBuy={handleBuy}
          onSell={handleSell}
        />
      )}
    </div>
  )
}
