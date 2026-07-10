import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { UsAnalysisItem, UsMarketStatus, UsWatchSignals } from '../types'

/**
 * 美股頁：Phase 2 基本技術狀態 + Phase 3 觀察訊號。
 * **非推薦、非買賣建議、非策略、無下單**；缺 key 或無資料時誠實顯示。
 */
export default function UsMarketPage() {
  const [status, setStatus] = useState<UsMarketStatus | null>(null)
  const [items, setItems] = useState<UsAnalysisItem[]>([])
  const [signals, setSignals] = useState<UsWatchSignals | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([api.getUsMarketStatus(), api.getUsAnalysis(), api.getUsSignals()])
      .then(([s, a, sig]) => { if (alive) { setStatus(s); setItems(a); setSignals(sig) } })
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
        <h2 className="page-subtitle">美股 · US Market（Phase 2：基本技術狀態）</h2>
      </div>

      {!sourceReady && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 16 }}>
          <div className="alert-title">美股資料源尚未就緒</div>
          <div className="alert-meta">
            目前資料源（{status?.source_label ?? 'US'}）尚未就緒；請確認設定後執行 <code>{backfillCmd}</code>。
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
      {sourceReady && hasAnyData && status?.is_stale && (
        <div className="alert alert-stale" role="alert" style={{ marginBottom: 16 }}>
          <div className="alert-title">美股資料可能已過期</div>
          <div className="alert-meta">
            資料日 {status.last_data_as_of ?? '—'}
            {status.days_since_last != null ? `（落後約 ${status.days_since_last} 個交易日`
              + `${status.expected_trading_day ? `，預期最新 ${status.expected_trading_day}` : ''}）` : ''}
            。請重跑 <code>{backfillCmd}</code>。
          </div>
        </div>
      )}
      {sourceReady && hasAnyData && !status?.is_stale && (
        <p className="us-freshness">
          資料日 <strong>{status?.last_data_as_of ?? '—'}</strong>
          {status?.days_since_last === 0
            ? '（最新）'
            : status?.days_since_last != null
              ? `（${status.days_since_last} 個交易日前）`
              : ''}
        </p>
      )}

      <p className="us-note">
        以下為<strong>基本技術狀態</strong>（MA / RSI / 漲跌幅 / 距均線）；<strong>非買賣建議、非策略、無下單</strong>。
      </p>

      <table className="data-table">
        <thead>
          <tr>
            <th>Ticker</th><th>名稱</th><th>收盤</th><th>資料日</th>
            <th>MA20</th><th>MA60</th><th>RSI</th><th>20日%</th><th>距MA20</th><th>技術狀態</th>
          </tr>
        </thead>
        <tbody>
          {items.map(u => (
            <tr key={u.code}>
              <td><span className="td-id">{u.code}</span></td>
              <td>{u.name}</td>
              <td>{fmt(u.last_close)}</td>
              <td>{u.last_data_as_of ?? '—'}</td>
              <td>{fmt(u.ma20)}</td>
              <td>{fmt(u.ma60)}</td>
              <td>{u.rsi14 != null ? u.rsi14.toFixed(0) : '—'}</td>
              <td>{pct(u.change_20d_pct)}</td>
              <td>{pct(u.dist_ma20_pct)}</td>
              <td><span className={`us-status us-status-${u.status}`}>{u.status_label}</span></td>
            </tr>
          ))}
        </tbody>
      </table>

      {signals && (
        <section className="us-signals-section">
          <h3 className="us-section-title">觀察訊號</h3>
          <p className="us-note">
            大盤基準：{signals.market_note}。<strong>非推薦、非買賣建議、非策略、無下單</strong>；priority 僅為觀察排序。
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th><th>名稱</th><th>收盤</th><th>觀察訊號</th><th>優先度</th><th>理由</th><th>風險</th>
              </tr>
            </thead>
            <tbody>
              {signals.signals.map(s => (
                <tr key={s.code}>
                  <td><span className="td-id">{s.code}</span></td>
                  <td>{s.name}</td>
                  <td>{fmt(s.close)}</td>
                  <td><span className={`us-signal us-signal-${s.signal}`}>{s.signal_label}</span></td>
                  <td>{s.priority}</td>
                  <td className="us-cell-list">{s.reasons.join('、') || '—'}</td>
                  <td className="us-cell-list">{s.risk_notes.join('、') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  )
}

function fmt(n: number | null): string {
  return n != null ? n.toFixed(2) : '—'
}
function pct(n: number | null): string {
  return n != null ? `${n > 0 ? '+' : ''}${n.toFixed(1)}%` : '—'
}
