import { useEffect, useState } from 'react'
import { api } from '../api/client'
import ManualTradeModal from '../components/ManualTradeModal'
import EditTradeModal from '../components/EditTradeModal'
import TradeTable from '../components/TradeTable'
import type { BuyRequest, SellRequest, TradeIntegrityReport, TradeRecord, TradeUpdateRequest } from '../types'

export default function TradesPage() {
  const [trades, setTrades] = useState<TradeRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TradeRecord | null>(null)
  const [integrity, setIntegrity] = useState<TradeIntegrityReport | null>(null)
  const [msg, setMsg] = useState('')

  const refreshTrades = () =>
    Promise.all([api.getTrades(), api.getTradeIntegrity()])
      .then(([records, report]) => {
        setTrades(records)
        setIntegrity(report)
      })
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

  const handleUpdate = async (tradeId: string, req: TradeUpdateRequest) => {
    await api.updateTrade(tradeId, req)
    setMsg('交易紀錄已修正；費稅、持倉與資料檢查已重新計算。')
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
      {integrity?.performance_status === 'provisional' && (
        <div className="trade-integrity-banner" role="status">
          <strong>績效目前為暫估</strong>
          <span>{integrity.warning_count} 筆成交價超出同日行情，{integrity.unverified_count} 筆缺少同日行情。請逐筆核對後再解讀績效。</span>
        </div>
      )}
      {msg && <div className="run-msg trade-page-msg">{msg}</div>}
      <TradeTable
        trades={trades}
        integrity={new Map((integrity?.items ?? []).map(item => [item.trade_id, item]))}
        onEdit={setEditing}
      />
      {modalOpen && (
        <ManualTradeModal
          onClose={() => setModalOpen(false)}
          onBuy={handleBuy}
          onSell={handleSell}
        />
      )}
      {editing && (
        <EditTradeModal
          trade={editing}
          onClose={() => setEditing(null)}
          onSave={req => handleUpdate(editing.id, req)}
        />
      )}
    </div>
  )
}
