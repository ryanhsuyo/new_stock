import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { UsMarketStatus, UsUniverseItem } from '../types'

/**
 * 美股 Phase 1：只做清單 + 基本行情呈現。
 * 不含策略 / 訊號 / 推薦 / 下單；缺 key 或無資料時誠實顯示狀態。
 */
export default function UsMarketPage() {
  const [status, setStatus] = useState<UsMarketStatus | null>(null)
  const [universe, setUniverse] = useState<UsUniverseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([api.getUsMarketStatus(), api.getUsUniverse()])
      .then(([s, u]) => { if (alive) { setStatus(s); setUniverse(u) } })
      .catch(e => { if (alive) setError(e instanceof Error ? e.message : '載入失敗') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  if (loading) return <main className="app-main"><p className="page-loading">載入中…</p></main>
  if (error) return <main className="app-main"><div className="page-error">美股資料載入失敗：{error}</div></main>

  const sourceReady = Boolean(status?.source_configured)
  const hasAnyData = (status?.tickers_with_data ?? 0) > 0
  const backfillCmd = status?.backfill_command ?? 'cd backend && python3 scripts/backfill_ohlcv_us.py'

  return (
    <main className="app-main">
      <div className="page-actions">
        <h2 className="page-subtitle">美股 · US Market（Phase 1）</h2>
      </div>

      {!sourceReady && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 16 }}>
          <div className="alert-title">美股資料源尚未設定</div>
          <div className="alert-meta">
            需設定環境變數 <code>FINNHUB_API_KEY</code> 才能抓美股資料；設定後執行 <code>{backfillCmd}</code>。
          </div>
        </div>
      )}
      {sourceReady && !hasAnyData && (
        <div className="alert alert-stale" role="alert" style={{ marginBottom: 16 }}>
          <div className="alert-title">美股資料尚未更新</div>
          <div className="alert-meta">
            資料源已設定，但尚無 OHLCV。請執行 <code>{backfillCmd}</code>。
          </div>
        </div>
      )}

      <p className="us-note">
        此頁只做美股清單與基本行情呈現；<strong>不含策略、訊號、推薦或下單</strong>。
      </p>

      <table className="data-table">
        <thead>
          <tr><th>Ticker</th><th>名稱</th><th>最新收盤</th><th>資料日</th><th>狀態</th></tr>
        </thead>
        <tbody>
          {universe.map(u => (
            <tr key={u.code}>
              <td><span className="td-id">{u.code}</span></td>
              <td>{u.name}</td>
              <td>{u.last_close != null ? u.last_close.toFixed(2) : '—'}</td>
              <td>{u.last_data_as_of ?? '—'}</td>
              <td>{u.data_status === 'ok' ? `已更新（${u.row_count} 筆）` : '尚未更新'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}
