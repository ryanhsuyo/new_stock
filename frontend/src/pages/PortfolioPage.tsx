import { useEffect, useState } from 'react'
import { api } from '../api/client'
import DailyChecklist from '../components/DailyChecklist'
import PortfolioTable from '../components/PortfolioTable'
import SellModal from '../components/SellModal'
import type { HoldingAnalysis, PatternResult, Position, SellRequest, UniverseReportItem } from '../types'

// ── 持股分析顯示輔助 ──────────────────────────────────────────────────────

const SIGNAL_LABEL: Record<string, { text: string; cls: string }> = {
  hold:                { text: '持股續抱',    cls: 'sig-hold'    },
  take_profit_warning: { text: '停利觀察',    cls: 'sig-caution' },
  exit_warning:        { text: '出場警示',    cls: 'sig-sell'    },
  invalidated:         { text: '多頭失效',    cls: 'sig-sell'    },
  watchlist:           { text: '觀察中',      cls: 'sig-watch'   },
  ready_to_enter:      { text: '準備進場',    cls: 'sig-buy'     },
  entry_confirmed:     { text: '進場確認',    cls: 'sig-buy-strong' },
  DATA_MISSING:        { text: '資料不足',    cls: 'sig-na'      },
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

const TREND_LABEL: Record<string, string> = {
  up: '↑ 多頭', down: '↓ 空頭', neutral: '→ 盤整', unknown: '—',
}

const ACTION_STYLE: Record<string, string> = {
  exit: 'battle-risk',
  reduce: 'battle-caution',
  hold: 'battle-hold',
  wait_pullback: 'battle-watch',
  enter: 'battle-enter',
  long_watch: 'battle-long',
  avoid: 'battle-muted',
}

function PatternSummary({ pattern }: { pattern: PatternResult }) {
  if (pattern.pattern_type === 'none') return null
  const typeLabel   = PATTERN_LABEL[pattern.pattern_type] ?? pattern.pattern_type
  const statusInfo  = PATTERN_STATUS_LABEL[pattern.pattern_status] ?? { text: pattern.pattern_status, cls: '' }
  return (
    <span className={`pattern-badge ${statusInfo.cls}`} style={{ marginLeft: 6 }}>
      {typeLabel} · {statusInfo.text}
      {pattern.neckline != null && <> 頸線 {pattern.neckline}</>}
    </span>
  )
}

function fallbackBattlePlan(h: HoldingAnalysis) {
  const a = h.analysis
  if (a.signal === 'exit_warning' || a.signal === 'invalidated') {
    return {
      daily_action: 'exit',
      daily_action_label: '出場處理',
      daily_action_reason: a.no_buy_reason || '趨勢或支撐已破壞',
      daily_key_price: a.stop_price != null ? `停損 ${a.stop_price}` : '—',
      daily_invalidation: '重新站回 MA20/MA60 後再評估',
    }
  }
  if (a.signal === 'take_profit_warning') {
    return {
      daily_action: 'reduce',
      daily_action_label: '減碼觀察',
      daily_action_reason: a.no_buy_reason || '接近壓力區，先控風險',
      daily_key_price: a.old_wang_volume_low_price != null ? `爆量低 ${a.old_wang_volume_low_price}` : a.ma20 != null ? `MA20 ${a.ma20}` : '—',
      daily_invalidation: '跌破短均或關鍵支撐',
    }
  }
  return {
    daily_action: 'hold',
    daily_action_label: '續抱',
    daily_action_reason: '長線未轉弱，依關鍵支撐續抱',
    daily_key_price: a.old_wang_volume_low_price != null ? `爆量低 ${a.old_wang_volume_low_price}` : a.ma20 != null ? `MA20 ${a.ma20}` : '—',
    daily_invalidation: '跌破關鍵支撐後重算',
  }
}

function HoldingCard({
  h,
  report,
  onNavigateAnalysis,
}: {
  h: HoldingAnalysis
  report?: UniverseReportItem
  onNavigateAnalysis?: (code: string) => void
}) {
  const a   = h.analysis
  const sig = SIGNAL_LABEL[a.signal] ?? { text: a.signal, cls: 'sig-na' }
  const battle = report ?? fallbackBattlePlan(h)
  const battleCls = ACTION_STYLE[battle.daily_action ?? ''] ?? 'battle-muted'
  const checklist = report?.daily_checklist?.length ? report.daily_checklist : a.daily_checklist

  const pnlColor =
    h.unrealized_pnl == null ? '' :
    h.unrealized_pnl > 0 ? 'up' : h.unrealized_pnl < 0 ? 'down' : ''

  return (
    <div className="holding-card">
      {/* 頭部：股票代碼 + 名稱 + 訊號 */}
      <div className="holding-card-header">
        <span className="holding-code">{a.code}</span>
        <span className="holding-name">{a.name}</span>
        <span className={`signal-badge ${sig.cls}`}>{sig.text}</span>
        <span className="panel-score">評分 {a.score}</span>
        <PatternSummary pattern={a.pattern} />
      </div>

      <div className={`holding-battle-plan ${battleCls}`}>
        <div className="battle-main">
          <span>{battle.daily_action_label ?? '作戰觀察'}</span>
          <strong>{battle.daily_action_reason ?? a.no_buy_reason ?? '依技術位置續觀察'}</strong>
        </div>
        <div className="battle-meta">
          <span>關鍵 {battle.daily_key_price ?? '—'}</span>
          <span>{battle.daily_invalidation ?? '等待重新轉強或收盤確認'}</span>
        </div>
        {onNavigateAnalysis && (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onNavigateAnalysis(a.code)}
          >
            監控
          </button>
        )}
      </div>

      <DailyChecklist items={checklist} compact />

      {/* 趨勢 + 最新收盤 */}
      <div className="holding-card-meta">
        <span>長線：<strong>{TREND_LABEL[a.long_trend] ?? a.long_trend}</strong></span>
        <span>短線：<strong>{TREND_LABEL[a.short_trend] ?? a.short_trend}</strong></span>
        {a.close != null && <span>最新收盤 <strong>{a.close}</strong></span>}
        {a.as_of && <span className="analysis-date">資料日 {a.as_of}</span>}
      </div>

      {/* 成本 / 損益 */}
      <div className="holding-card-pnl">
        <span>均價 {h.avg_cost}</span>
        <span>持股 {h.shares} 股</span>
        {h.unrealized_pnl != null && (
          <span className={pnlColor}>
            未實現 {h.unrealized_pnl >= 0 ? '+' : ''}{h.unrealized_pnl.toLocaleString()}
            （{h.return_rate != null ? `${h.return_rate >= 0 ? '+' : ''}${h.return_rate}%` : '—'}）
          </span>
        )}
      </div>

      {/* 進場/持倉理由 */}
      {a.reasons.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-title">訊號依據</div>
          <ul className="panel-list">
            {a.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* 風險提示 */}
      {a.risk_notes.length > 0 && (
        <div className="panel-section panel-risk">
          <div className="panel-section-title">風險提示</div>
          <ul className="panel-list">
            {a.risk_notes.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* 不持倉理由（若非 hold，說明為何不是標準持倉訊號） */}
      {a.no_buy_reason && a.signal !== 'hold' && (
        <div className="panel-section">
          <div className="panel-section-title">注意事項</div>
          <p className="panel-no-buy">{a.no_buy_reason}</p>
        </div>
      )}

      {/* 資料不足提示 */}
      {!a.data_ok && (
        <div className="panel-section panel-risk">
          <p>{a.data_missing_reason}</p>
        </div>
      )}
    </div>
  )
}

// ── 主頁面 ───────────────────────────────────────────────────────────────

interface Props {
  onNavigateAnalysis?: (code: string) => void
}

export default function PortfolioPage({ onNavigateAnalysis }: Props) {
  const [positions, setPositions]           = useState<Position[]>([])
  const [holdings, setHoldings]             = useState<HoldingAnalysis[]>([])
  const [reportItems, setReportItems]       = useState<UniverseReportItem[]>([])
  const [loadingPos, setLoadingPos]         = useState(true)
  const [loadingAnalysis, setLoadingAnalysis] = useState(true)
  const [error, setError]                   = useState('')
  const [sellTarget, setSellTarget]         = useState<Position | null>(null)

  const loadPositions = () => {
    setLoadingPos(true)
    api.getPortfolio()
      .then(setPositions)
      .catch(e => setError(e.message))
      .finally(() => setLoadingPos(false))
  }

  const loadAnalysis = () => {
    setLoadingAnalysis(true)
    api.getPortfolioAnalysis()
      .then(setHoldings)
      .catch(() => setHoldings([]))   // 分析失敗不中斷主流程
      .finally(() => setLoadingAnalysis(false))
  }

  const loadReport = () => {
    api.getUniverseReportOrNull()
      .then(rows => setReportItems(rows ?? []))
      .catch(() => setReportItems([]))
  }

  useEffect(() => {
    loadPositions()
    loadAnalysis()
    loadReport()
  }, [])

  const handleSellSubmit = async (req: SellRequest) => {
    await api.sellStock(req)
    loadPositions()
    loadAnalysis()
    loadReport()
  }

  const reportByCode = new Map(reportItems.map(item => [item.code, item]))
  const sortedHoldings = [...holdings].sort((a, b) => {
    const pa = reportByCode.get(a.analysis.code)?.daily_priority ?? 50
    const pb = reportByCode.get(b.analysis.code)?.daily_priority ?? 50
    return pb - pa
  })

  if (loadingPos) return <p className="page-loading">載入中…</p>
  if (error) return <p className="page-error">{error}</p>

  return (
    <div>
      {/* 持倉總覽 */}
      <h2 className="page-subtitle">目前持倉</h2>
      <PortfolioTable positions={positions} onSell={setSellTarget} />

      {sellTarget && (
        <SellModal
          position={sellTarget}
          onClose={() => setSellTarget(null)}
          onSubmit={handleSellSubmit}
        />
      )}

      {/* 持股技術分析 */}
      <div className="holding-analysis-section">
        <h2 className="page-subtitle" style={{ marginBottom: 12 }}>持股技術分析</h2>

        {loadingAnalysis ? (
          <p className="page-loading">分析中…</p>
        ) : holdings.length === 0 ? (
          <p className="empty-hint">無持股資料（請先在交易紀錄中新增買入，持股會由 trades.json 自動推算）</p>
        ) : (
          <div className="holding-cards">
            {sortedHoldings.map(h => (
              <HoldingCard
                key={h.analysis.code}
                h={h}
                report={reportByCode.get(h.analysis.code)}
                onNavigateAnalysis={onNavigateAnalysis}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
