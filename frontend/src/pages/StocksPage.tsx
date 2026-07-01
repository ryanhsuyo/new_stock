import { useEffect, useState } from 'react'
import { api } from '../api/client'
import BuyModal from '../components/BuyModal'
import NoSignalExplainer from '../components/NoSignalExplainer'
import StockCard from '../components/StockCard'
import type { BuyRequest, SignalsSummary, StockRecommendation } from '../types'

interface Props {
  onNavigateAnalysis?: (code: string) => void
}

export default function StocksPage({ onNavigateAnalysis }: Props) {
  const [stocks, setStocks]   = useState<StockRecommendation[]>([])
  const [summary, setSummary] = useState<SignalsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [buyTarget, setBuyTarget] = useState<StockRecommendation | null | 'manual'>(undefined as never)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    Promise.all([
      api.getRecommendations(),
      api.getSummaryOrNull(),
    ])
      .then(([recs, sm]) => { setStocks(recs); setSummary(sm) })
      .catch(e => setError(e instanceof Error ? e.message : '載入失敗'))
      .finally(() => setLoading(false))
  }, [])

  const openBuy = (stock: StockRecommendation | null) => {
    setBuyTarget(stock)
    setModalOpen(true)
  }

  const handleBuySubmit = async (req: BuyRequest) => {
    await api.buyStock(req)
  }

  if (loading) return <p className="page-loading">載入中…</p>
  if (error) return <p className="page-error">{error}</p>

  return (
    <div>
      <div className="page-actions">
        <h2 className="page-subtitle">本週推薦（{stocks.length} 支）</h2>
        <button className="btn btn-ghost" onClick={() => openBuy(null)}>
          + 手動記錄買入
        </button>
      </div>

      <div className="weekly-recommendation-note">
        <strong>正式推薦以週為單位</strong>
        <span>
          每日盤後掃描只用來更新候選、風險與進出場提醒；今日異動請看 Dashboard / Today Scan，
          本頁保留本週主要觀察與可執行標的，避免每天追價換單。
        </span>
      </div>

      {stocks.length === 0 && (
        summary
          ? <NoSignalExplainer summary={summary} />
          : <p className="empty-hint">目前無推薦，請先在「訊號 Dashboard」產生訊號。</p>
      )}

      <div className="stock-grid">
        {stocks.map(s => (
          <StockCard key={s.stock_id} stock={s} onBuy={openBuy} onAnalysis={onNavigateAnalysis} />
        ))}
      </div>

      {modalOpen && (
        <BuyModal
          stock={buyTarget as StockRecommendation | null}
          onClose={() => setModalOpen(false)}
          onSubmit={handleBuySubmit}
        />
      )}
    </div>
  )
}
