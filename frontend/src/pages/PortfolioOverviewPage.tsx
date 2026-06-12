import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DataStatus, HoldingAnalysis, PatternResult, PortfolioSummary } from '../types'

// ── 常數對照表 ────────────────────────────────────────────────────────────

const SIGNAL_LABEL: Record<string, { text: string; cls: string }> = {
  hold:                { text: '持股續抱', cls: 'sig-hold'      },
  take_profit_warning: { text: '停利觀察', cls: 'sig-caution'   },
  exit_warning:        { text: '出場警示', cls: 'sig-sell'      },
  invalidated:         { text: '多頭失效', cls: 'sig-sell'      },
  watchlist:           { text: '觀察中',   cls: 'sig-watch'     },
  ready_to_enter:      { text: '準備進場', cls: 'sig-buy'       },
  entry_confirmed:     { text: '進場確認', cls: 'sig-buy-strong'},
  DATA_MISSING:        { text: '資料不足', cls: 'sig-na'        },
}

// 訊號緊急度排序（數字小 = 越緊急，升冪排列時最緊急排最前）
const SIGNAL_URGENCY: Record<string, number> = {
  exit_warning: 0, invalidated: 1, take_profit_warning: 2,
  hold: 3, watchlist: 4, ready_to_enter: 5, entry_confirmed: 6, DATA_MISSING: 7,
}

const PATTERN_LABEL: Record<string, string> = {
  w_bottom: 'W底', m_top: 'M頂', none: '',
}
const PATTERN_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  forming:   { text: '形成中', cls: 'pst-forming'   },
  confirmed: { text: '已確認', cls: 'pst-confirmed' },
  failed:    { text: '已失效', cls: 'pst-failed'    },
  none:      { text: '',       cls: ''               },
}

// ── 排序相關型別 ─────────────────────────────────────────────────────────

type SortKey = 'signal' | 'pnl' | 'return_rate'
type SortDir = 'asc' | 'desc'

function sortHoldings(list: HoldingAnalysis[], key: SortKey | null, dir: SortDir) {
  if (!key) return list
  return [...list].sort((a, b) => {
    let diff = 0
    if (key === 'signal') {
      diff = (SIGNAL_URGENCY[a.analysis.signal] ?? 99) - (SIGNAL_URGENCY[b.analysis.signal] ?? 99)
    } else if (key === 'pnl') {
      diff = (a.unrealized_pnl ?? 0) - (b.unrealized_pnl ?? 0)
    } else {
      diff = (a.return_rate ?? 0) - (b.return_rate ?? 0)
    }
    return dir === 'asc' ? diff : -diff
  })
}

// ── 輔助元件 ──────────────────────────────────────────────────────────────

function fmt(n: number, digits = 0) {
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })
}
function fmtDatetime(s: string | null) {
  if (!s) return '—'
  return s.slice(0, 16).replace('T', ' ')
}

function PnlCell({ value }: { value: number | null }) {
  if (value == null) return <span className="flat">—</span>
  const cls = value > 0 ? 'up' : value < 0 ? 'down' : 'flat'
  return <span className={cls}>{value >= 0 ? '+' : ''}{fmt(value)}</span>
}

function PatternCell({ pattern }: { pattern: PatternResult }) {
  if (pattern.pattern_type === 'none') return <span className="flat">—</span>
  const typeLabel  = PATTERN_LABEL[pattern.pattern_type] ?? pattern.pattern_type
  const statusInfo = PATTERN_STATUS_LABEL[pattern.pattern_status] ?? { text: pattern.pattern_status, cls: '' }
  return (
    <span className={`pattern-badge ${statusInfo.cls}`}>
      {typeLabel}{statusInfo.text ? ` · ${statusInfo.text}` : ''}
    </span>
  )
}

function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="sort-ind">↕</span>
  return <span className="sort-ind sort-ind-active">{dir === 'asc' ? '↑' : '↓'}</span>
}

// ── 資料新鮮度列（含 running 狀態） ──────────────────────────────────────

function FreshnessSection({ status }: { status: DataStatus }) {
  const isStale   = status.is_stale
  const hasFailed = status.last_run_status === 'failed'
  const isRunning = status.last_run_status === 'running'
  const bannerCls = `freshness-bar${isStale ? ' freshness-stale' : ' freshness-ok'}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* 更新中 banner */}
      {isRunning && (
        <div className="alert alert-running" role="status">
          <div className="alert-title">
            <span className="spinner" aria-hidden="true" />
            資料更新中，請稍候…
          </div>
          <div className="alert-meta">開始時間：{fmtDatetime(status.last_run_started_at)}</div>
        </div>
      )}

      <div className="alert alert-info" role="note">
        <div className="alert-title">價格基準：{status.price_basis_label ?? '最新收盤價'}</div>
        <div className="alert-meta">
          {status.price_basis_note ?? '投組估值與正式訊號使用最新收盤價，不是盤中即時市價。'}
        </div>
      </div>

      {/* stale 警示（更新成功但資料已舊） */}
      {isStale && !hasFailed && !isRunning && (
        <div className="alert alert-stale alert-stale-prominent" role="alert">
          <div className="alert-title">
            資料已 {status.stale_days != null ? `${status.stale_days} 天` : '數天'}未更新，訊號可能不準確
          </div>
          <div className="alert-meta">
            資料最新日：<strong>{status.last_data_as_of ?? '—'}</strong>
            　請執行 <code>python scripts/update_all_data.py</code> 或等待排程更新
          </div>
        </div>
      )}

      {/* 更新失敗警示 */}
      {hasFailed && (
        <div className="alert alert-error" role="alert">
          <div className="alert-title">
            更新失敗
            {status.last_error_summary && (
              <span className="alert-error-summary">：{status.last_error_summary}</span>
            )}
          </div>
          <div className="alert-meta">
            失敗時間：{fmtDatetime(status.last_run_finished_at)}
            {isStale && (
              <span>
                　　資料最新日：{status.last_data_as_of ?? '—'}
                （已 {status.stale_days} 天未更新）
              </span>
            )}
          </div>
          {status.last_error && (
            <details className="alert-details">
              <summary>查看完整錯誤訊息</summary>
              <pre className="alert-error-detail">{status.last_error}</pre>
            </details>
          )}
        </div>
      )}

      {/* 新鮮度資訊列 */}
      <div className={bannerCls}>
        <div className="freshness-item">
          <span className="freshness-label">資料最新日</span>
          <span className="freshness-value">{status.last_data_as_of ?? '—'}</span>
        </div>
        <div className="freshness-item">
          <span className="freshness-label">距今天數</span>
          <span className="freshness-value">
            {status.stale_days != null ? `${status.stale_days} 天` : '—'}
            {isStale && <span className="freshness-warn"> ⚠</span>}
          </span>
        </div>
        <div className="freshness-item">
          <span className="freshness-label">最後更新</span>
          <span className="freshness-value">{fmtDatetime(status.last_run_finished_at)}</span>
        </div>
        <div className="freshness-item">
          <span className="freshness-label">更新狀態</span>
          <span className={`freshness-status ${
            status.last_run_status === 'success' ? 'freshness-success'
            : status.last_run_status === 'failed'  ? 'freshness-failed'
            : status.last_run_status === 'running' ? 'freshness-running'
            : 'freshness-unknown'
          }`}>
            {status.last_run_status === 'success' ? '✓ 成功'
              : status.last_run_status === 'failed'  ? '✗ 失敗'
              : status.last_run_status === 'running' ? <><span className="spinner spinner-sm" />執行中</>
              : '未執行'}
          </span>
        </div>
      </div>

    </div>
  )
}

// ── 投組摘要區 ────────────────────────────────────────────────────────────

function SummarySection({ s }: { s: PortfolioSummary }) {
  const pnlCls = s.total_unrealized_pnl > 0 ? 'up' : s.total_unrealized_pnl < 0 ? 'down' : 'flat'
  return (
    <div>
      <div className="stats-grid overview-stats-grid">
        <div className="stat-card">
          <div className="stat-label">持股檔數</div>
          <div className="stat-value neutral">{s.total_positions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">總成本</div>
          <div className="stat-value neutral">{fmt(s.total_cost)} 元</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">收盤估值</div>
          <div className="stat-value neutral">{fmt(s.total_market_value)} 元</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">未實現損益</div>
          <div className={`stat-value ${pnlCls}`}>
            {s.total_unrealized_pnl >= 0 ? '+' : ''}{fmt(s.total_unrealized_pnl)} 元
          </div>
        </div>
      </div>
      <div className="overview-sig-section">
        <div className="overview-sig-title">訊號分佈</div>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">持股續抱</div>
            <div className="stat-value neutral">{s.hold_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">停利觀察</div>
            <div className={`stat-value ${s.take_profit_warning_count > 0 ? 'overview-caution' : 'neutral'}`}>
              {s.take_profit_warning_count}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">出場警示</div>
            <div className={`stat-value ${s.exit_warning_count > 0 ? 'down' : 'neutral'}`}>
              {s.exit_warning_count}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">多頭失效</div>
            <div className={`stat-value ${s.invalidated_count > 0 ? 'down' : 'neutral'}`}>
              {s.invalidated_count}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── 持股清單表格（支援排序 + 點擊跳轉） ─────────────────────────────────

function HoldingsTable({
  holdings,
  onNavigateAnalysis,
}: {
  holdings: HoldingAnalysis[]
  onNavigateAnalysis?: (code: string) => void
}) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  if (holdings.length === 0) {
    return <p className="empty-hint">無持股紀錄（請先從推薦清單記錄買入）</p>
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      // 同欄位：asc → desc → 取消排序
      if (sortDir === 'asc') setSortDir('desc')
      else { setSortKey(null); setSortDir('asc') }
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sorted = sortHoldings(holdings, sortKey, sortDir)

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>股票</th>
            <th>持股</th>
            <th>均價</th>
            <th>最新收盤</th>
            <th className="th-sortable" onClick={() => handleSort('pnl')} title="點擊排序">
              未實現損益 <SortIndicator active={sortKey === 'pnl'} dir={sortDir} />
            </th>
            <th className="th-sortable" onClick={() => handleSort('return_rate')} title="點擊排序">
              報酬率 <SortIndicator active={sortKey === 'return_rate'} dir={sortDir} />
            </th>
            <th className="th-sortable" onClick={() => handleSort('signal')} title="點擊排序（依緊急度）">
              訊號 <SortIndicator active={sortKey === 'signal'} dir={sortDir} />
            </th>
            <th>型態</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(h => {
            const a   = h.analysis
            const sig = SIGNAL_LABEL[a.signal] ?? { text: a.signal, cls: 'sig-na' }
            const rateCls = h.return_rate != null && h.return_rate > 0 ? 'up'
                          : h.return_rate != null && h.return_rate < 0 ? 'down' : 'flat'
            return (
              <tr key={a.code}>
                <td>
                  {onNavigateAnalysis ? (
                    <button
                      className="link-btn"
                      onClick={() => onNavigateAnalysis(a.code)}
                      title={`查看 ${a.name}（${a.code}）技術分析`}
                    >
                      <span className="td-name">{a.name}</span>
                      <span className="td-id">{a.code}</span>
                    </button>
                  ) : (
                    <>
                      <span className="td-name">{a.name}</span>
                      <span className="td-id">{a.code}</span>
                    </>
                  )}
                </td>
                <td>{h.shares.toLocaleString()}</td>
                <td>{h.avg_cost.toFixed(2)}</td>
                <td>{a.close != null ? a.close.toFixed(2) : '—'}</td>
                <td><PnlCell value={h.unrealized_pnl} /></td>
                <td>
                  {h.return_rate != null
                    ? <span className={rateCls}>{h.return_rate >= 0 ? '+' : ''}{h.return_rate.toFixed(2)}%</span>
                    : <span className="flat">—</span>}
                </td>
                <td>
                  <span className={`signal-badge ${sig.cls}`}>{sig.text}</span>
                </td>
                <td><PatternCell pattern={a.pattern} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── 主頁面 ────────────────────────────────────────────────────────────────

interface Props {
  onNavigateAnalysis?: (code: string) => void
}

export default function PortfolioOverviewPage({ onNavigateAnalysis }: Props) {
  const [summary, setSummary]       = useState<PortfolioSummary | null>(null)
  const [holdings, setHoldings]     = useState<HoldingAnalysis[]>([])
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)
  const [loading, setLoading]       = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [updating, setUpdating]     = useState(false)
  const [error, setError]           = useState('')

  async function loadData() {
    const [s, h, ds] = await Promise.all([
      api.getPortfolioSummary(),
      api.getPortfolioAnalysis(),
      api.getDataStatus(),
    ])
    setSummary(s)
    setHoldings(h)
    setDataStatus(ds)
  }

  // 初始載入
  useEffect(() => {
    setLoading(true)
    loadData()
      .catch(e => setError(e instanceof Error ? e.message : '載入失敗'))
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 當 status = running 時，每 3 秒 poll 一次；完成後全量刷新
  useEffect(() => {
    if (dataStatus?.last_run_status !== 'running') {
      setUpdating(false)
      return
    }
    const timer = setInterval(() => {
      api.getDataStatus()
        .then(ds => {
          setDataStatus(ds)
          if (ds.last_run_status !== 'running') {
            setUpdating(false)
            // 更新完成，刷新持倉與摘要
            Promise.all([api.getPortfolioSummary(), api.getPortfolioAnalysis()])
              .then(([s, h]) => { setSummary(s); setHoldings(h) })
              .catch(() => {})
          }
        })
        .catch(() => {})
    }, 3000)
    return () => clearInterval(timer)
  }, [dataStatus?.last_run_status])

  async function handleUpdateNow() {
    if (refreshing || updating || dataStatus?.last_run_status === 'running') return
    setError('')
    setUpdating(true)
    try {
      await api.triggerUpdateNow()
      setDataStatus(prev => prev
        ? { ...prev, last_run_status: 'running', last_run_started_at: new Date().toISOString().slice(0, 19) }
        : prev
      )
    } catch (e: unknown) {
      setUpdating(false)
      const msg = e instanceof Error ? e.message : '觸發更新失敗'
      if (msg.includes('已在執行中') || msg.includes('running')) {
        setDataStatus(prev => prev ? { ...prev, last_run_status: 'running' } : prev)
      } else {
        setError(msg)
      }
    }
  }

  function handleRefresh() {
    if (refreshing) return
    setRefreshing(true)
    setError('')
    loadData()
      .catch(e => setError(e instanceof Error ? e.message : '載入失敗'))
      .finally(() => setRefreshing(false))
  }

  if (loading) return <p className="page-loading">載入中…</p>
  if (error)   return <p className="page-error">{error}</p>

  return (
    <div className="overview-page">

      {/* 頁面標題 + 操作按鈕 */}
      <div className="overview-toolbar">
        <h2 className="page-subtitle">投組總覽</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {error && <span className="form-error" style={{ fontSize: 13 }}>{error}</span>}
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleUpdateNow}
            disabled={refreshing || updating || dataStatus?.last_run_status === 'running'}
            title="觸發後端 backfill + signals 全流程更新"
          >
            {(updating || dataStatus?.last_run_status === 'running')
              ? <><span className="spinner spinner-sm" aria-hidden="true" />更新中…</>
              : '立即更新資料'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleRefresh}
            disabled={refreshing || updating || dataStatus?.last_run_status === 'running'}
            title="重新載入資料"
          >
            {refreshing
              ? <><span className="spinner spinner-sm" aria-hidden="true" />載入中…</>
              : '⟳ 重新整理'}
          </button>
        </div>
      </div>

      {/* 資料新鮮度 */}
      {dataStatus && <FreshnessSection status={dataStatus} />}

      {/* 投組摘要 */}
      {summary && (
        <section className="overview-section">
          <h2 className="page-subtitle">投組摘要</h2>
          <SummarySection s={summary} />
        </section>
      )}

      {/* 持股清單（可排序 + 可點擊跳轉技術分析） */}
      <section className="overview-section">
        <h2 className="page-subtitle">
          持股清單
          <span className="overview-sort-hint">（訊號／損益／報酬率欄可點擊排序）</span>
        </h2>
        <HoldingsTable holdings={holdings} onNavigateAnalysis={onNavigateAnalysis} />
      </section>

    </div>
  )
}
