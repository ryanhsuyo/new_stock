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
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

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

  // 觀察用分類（依 leaders.json 出現順序，非推薦分組）
  const categories = items.reduce<string[]>((acc, u) => {
    if (u.category && !acc.includes(u.category)) acc.push(u.category)
    return acc
  }, [])
  const matchCat = (c: string) => categoryFilter === 'all' || c === categoryFilter
  const shownItems = items.filter(u => matchCat(u.category))
  const shownSignals = signals?.signals.filter(s => matchCat(s.category)) ?? []

  // 資料狀態面板：回補是否補齊一眼可判（missing / insufficient / min_row_count）
  const missing = status?.missing_tickers ?? []
  const insufficient = status?.insufficient_tickers ?? []
  const dataComplete = hasAnyData && missing.length === 0 && insufficient.length === 0
  // 手動更新指令（只顯示，不執行；--months 12 為完整回補）
  const backfillFullCmd = `${backfillCmd} --months 12`

  return (
    <main className="app-main">
      <div className="page-actions">
        <h2 className="page-subtitle">美股 · US Market（觀察用：技術狀態 / 觀察訊號，非推薦）</h2>
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
      {/* 資料狀態面板：資料源 / 覆蓋率 / 新鮮度 / 回補缺口，指令只顯示不執行 */}
      {status && (
        <section className="us-data-panel" aria-label="美股資料狀態">
          <div className="us-data-panel-head">
            <span className="us-data-panel-title">資料狀態</span>
            <span className={`us-data-pill ${dataComplete ? 'us-data-pill-ok' : 'us-data-pill-warn'}`}>
              {dataComplete && status.min_row_count != null
                ? `${status.tickers_with_data}/${status.universe_size} 已更新，最少 ${status.min_row_count} 筆`
                : `${status.tickers_with_data}/${status.universe_size} 已更新`}
            </span>
          </div>
          <dl className="us-data-grid">
            <div className="us-data-item">
              <dt>資料源</dt>
              <dd>{status.source_label ?? 'US'}</dd>
            </div>
            <div className="us-data-item">
              <dt>資料日</dt>
              <dd>
                {status.last_data_as_of ?? '—'}
                {status.days_since_last === 0
                  ? '（最新）'
                  : status.days_since_last != null
                    ? `（${status.days_since_last} 個交易日前）`
                    : ''}
                {status.is_stale && <span className="us-data-stale-tag">已過期</span>}
              </dd>
            </div>
            <div className="us-data-item">
              <dt>最少筆數</dt>
              <dd>{status.min_row_count != null ? `${status.min_row_count} 筆` : '—'}</dd>
            </div>
          </dl>
          {missing.length > 0 && (
            <p className="us-data-issue">
              <strong>無資料（{missing.length}）：</strong>{missing.join('、')}
            </p>
          )}
          {insufficient.length > 0 && (
            <p className="us-data-issue">
              <strong>筆數不足（{insufficient.length}，&lt; 60 筆無法算 MA60）：</strong>{insufficient.join('、')}
            </p>
          )}
          <p className="us-data-cmd">
            手動更新（本機終端機執行）：<code>{backfillFullCmd}</code>
          </p>
        </section>
      )}

      <p className="us-note">
        以下為<strong>基本技術狀態</strong>（MA / RSI / 漲跌幅 / 距均線）；<strong>非買賣建議、非策略、無下單</strong>。
      </p>
      <p className="us-note us-status-legend">
        <span className="us-status us-status-trend_up">趨勢向上</span> 站上 MA20，均線已翻多
        <span className="us-status us-status-recovering">趨勢修復中</span> 站上 MA20 / MA60，但 MA20 仍在 MA60 下方
        <span className="us-status us-status-pullback_watch">回檔觀察</span> 跌破 MA20，仍守 MA60
        <span className="us-status us-status-overheated">過熱</span> RSI 偏高或距 MA20 過遠
        <span className="us-status us-status-weak">弱勢</span> 跌破 MA60
        <span className="us-status us-status-no_data">資料不足</span> 指標算不出來（非弱勢）
      </p>

      {categories.length > 1 && (
        <div className="us-cat-filter" role="group" aria-label="分類過濾">
          <button
            type="button"
            className={`us-cat-chip${categoryFilter === 'all' ? ' is-active' : ''}`}
            onClick={() => setCategoryFilter('all')}
          >
            全部（{items.length}）
          </button>
          {categories.map(cat => {
            const n = items.filter(u => u.category === cat).length
            return (
              <button
                key={cat}
                type="button"
                className={`us-cat-chip${categoryFilter === cat ? ' is-active' : ''}`}
                onClick={() => setCategoryFilter(cat)}
              >
                {cat}（{n}）
              </button>
            )
          })}
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Ticker</th><th>名稱</th><th>分類</th><th>收盤</th><th>資料日</th>
            <th>MA20</th><th>MA60</th><th>RSI</th><th>20日%</th><th>距MA20</th><th>技術狀態</th>
          </tr>
        </thead>
        <tbody>
          {shownItems.map(u => (
            <tr key={u.code}>
              <td><span className="td-id">{u.code}</span></td>
              <td>{u.name}</td>
              <td><span className="us-cat-tag">{u.category || '—'}</span></td>
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
                <th>Ticker</th><th>名稱</th><th>分類</th><th>收盤</th><th>觀察訊號</th><th>優先度</th><th>理由</th><th>風險</th>
              </tr>
            </thead>
            <tbody>
              {shownSignals.map(s => (
                <tr key={s.code}>
                  <td><span className="td-id">{s.code}</span></td>
                  <td>{s.name}</td>
                  <td><span className="us-cat-tag">{s.category || '—'}</span></td>
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
