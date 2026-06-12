import type { PatternResult, StockAnalysis } from '../types'
import DailyChecklist from './DailyChecklist'

interface Props {
  data: StockAnalysis
}

const SIGNAL_LABEL: Record<string, { text: string; cls: string }> = {
  entry_confirmed:     { text: '進場確認', cls: 'sig-buy-strong' },
  ready_to_enter:      { text: '準備進場', cls: 'sig-buy' },
  watchlist:           { text: '觀察中',   cls: 'sig-watch' },
  hold:                { text: '持股續抱', cls: 'sig-hold' },
  take_profit_warning: { text: '停利觀察', cls: 'sig-caution' },
  exit_warning:        { text: '警示出場', cls: 'sig-sell' },
  invalidated:         { text: '多頭失效', cls: 'sig-sell' },
  DATA_MISSING:        { text: '資料不足', cls: 'sig-na' },
}

const PATTERN_LABEL: Record<string, string> = {
  w_bottom: 'W底',
  m_top:    'M頂',
  none:     '',
}

const PATTERN_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  forming:   { text: '形成中', cls: 'pst-forming'   },
  confirmed: { text: '已確認', cls: 'pst-confirmed' },
  failed:    { text: '已失效', cls: 'pst-failed'    },
  none:      { text: '',       cls: ''               },
}

function PatternBadge({ pattern }: { pattern: PatternResult }) {
  if (pattern.pattern_type === 'none') return null
  const typeLabel   = PATTERN_LABEL[pattern.pattern_type] ?? pattern.pattern_type
  const statusInfo  = PATTERN_STATUS_LABEL[pattern.pattern_status] ?? { text: pattern.pattern_status, cls: '' }
  return (
    <div className="pattern-row">
      <span className={`pattern-badge ${statusInfo.cls}`}>
        {typeLabel} · {statusInfo.text}
      </span>
      {pattern.neckline != null && (
        <span className="pattern-neckline">頸線 {pattern.neckline}</span>
      )}
      {pattern.note && <span className="pattern-note">{pattern.note}</span>}
    </div>
  )
}

const TREND_LABEL: Record<string, string> = {
  up: '↑ 多頭',
  down: '↓ 空頭',
  neutral: '→ 盤整',
  unknown: '—',
}

const DAILY_ACTION_CLASS: Record<string, string> = {
  enter: 'decision-enter',
  wait_pullback: 'decision-wait',
  hold: 'decision-hold',
  reduce: 'decision-reduce',
  exit: 'decision-exit',
  avoid: 'decision-avoid',
  long_watch: 'decision-watch',
}

function fmtPrice(v: number | null | undefined) {
  return v == null ? '—' : v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function hasOldWangTag(data: StockAnalysis) {
  return data.old_wang_flag === true || data.old_wang_tag === 'old_wang_market_chip_rotation'
}

function hasCoreEntry(data: StockAnalysis) {
  return data.signal === 'entry_confirmed' || data.signal === 'ready_to_enter'
}

function getStrategyPlan(data: StockAnalysis) {
  const core = hasCoreEntry(data)
  const oldWang = hasOldWangTag(data)

  if (!data.data_ok || data.signal === 'DATA_MISSING') {
    return { title: '無方案', cls: 'plan-muted', advice: '資料不足', detail: data.data_missing_reason || '先補資料' }
  }
  if (data.old_wang_previous_high_risk) {
    return { title: '老王風險', cls: 'plan-risk', advice: '不建議進場', detail: '5/10/20/60 全破，前高型態風險成立' }
  }
  if (core && oldWang) {
    return {
      title: '雙重共振',
      cls: 'plan-strong',
      advice: data.signal === 'entry_confirmed' ? '可小量試單' : '等區間分批',
      detail: '核心買點 + 老王均線支撐',
    }
  }
  if (oldWang) {
    return {
      title: '老王觀察',
      cls: 'plan-wang',
      advice: '不追高，等 5/10',
      detail: data.old_wang_volume_low_support
        ? `守大量低點 ${fmtPrice(data.old_wang_volume_low_price)}`
        : data.old_wang_gap_type === 'gap_up'
          ? `守跳空支撐 ${fmtPrice(data.old_wang_gap_support)}`
          : '短線止跌再分批',
    }
  }
  if (core) {
    return {
      title: '核心策略',
      cls: 'plan-core',
      advice: data.signal === 'entry_confirmed' ? '可小量試單' : '等區間分批',
      detail: data.price_plan_note || '依進場區間執行',
    }
  }
  if (data.signal === 'take_profit_warning') {
    return { title: '停利觀察', cls: 'plan-watch', advice: '不追價', detail: data.no_buy_reason || '等待回測或短均線轉弱' }
  }
  if (['exit_warning', 'invalidated'].includes(data.signal)) {
    return { title: '無方案', cls: 'plan-risk', advice: '暫不進場', detail: data.no_buy_reason || '風險訊號' }
  }
  return { title: '觀察方案', cls: 'plan-watch', advice: '等條件成立', detail: data.no_buy_reason || data.price_plan_note || '尚未到進場點' }
}

export default function AnalysisPanel({ data }: Props) {
  const sig = SIGNAL_LABEL[data.signal] ?? { text: data.signal, cls: 'sig-na' }
  const plan = getStrategyPlan(data)
  const hasDailyAction = Boolean(data.daily_action_label || data.daily_action_reason)
  const dailyActionClass = DAILY_ACTION_CLASS[data.daily_action ?? ''] ?? 'decision-muted'

  return (
    <div className="analysis-panel">
      {/* 訊號 + 基本指標 */}
      <div className="panel-row panel-header-row">
        <div>
          <span className={`signal-badge ${sig.cls}`}>{sig.text}</span>
          <span className="panel-score">評分 {data.score}</span>
        </div>
        <div className="panel-meta">
          <span>長線：<strong>{TREND_LABEL[data.long_trend] ?? data.long_trend}</strong></span>
          <span>短線：<strong>{TREND_LABEL[data.short_trend] ?? data.short_trend}</strong></span>
        </div>
      </div>

      <div className="analysis-strategy-box">
        <div>
          <span className={`plan-badge ${plan.cls}`}>{plan.title}</span>
          <strong>{plan.advice}</strong>
          <span>{plan.detail}</span>
        </div>
        {hasOldWangTag(data) && (
          <div className="analysis-strategy-meta">
            <span>老王 {data.old_wang_score ?? '—'}</span>
            {data.old_wang_raw_score != null && <span>原始 {data.old_wang_raw_score}</span>}
            <span>{data.old_wang_support_state}</span>
            {data.old_wang_parabolic_ma10_hold && <span>噴出看 MA10</span>}
            {data.old_wang_all_ma_reclaim && <span>四海遊龍</span>}
            {data.old_wang_volume_high_breakout && <span>爆量高突破 {fmtPrice(data.old_wang_volume_high_price)}</span>}
            {data.old_wang_previous_high_state && data.old_wang_previous_high_state !== 'none' && (
              <span>
                前高{data.old_wang_previous_high_state === 'breakout'
                  ? '突破'
                  : data.old_wang_previous_high_state === 'failed'
                    ? '回檔'
                    : '接近'} {fmtPrice(data.old_wang_previous_high_price)}
              </span>
            )}
            <span>籌碼 {data.old_wang_chip_signal}</span>
            {data.old_wang_sector && <span>{data.old_wang_sector}</span>}
          </div>
        )}
      </div>

      {hasDailyAction && (
        <div className="analysis-daily-action">
          <div>
            <span className={`decision-badge ${dailyActionClass}`}>
              {data.daily_action_label || '今日觀察'}
            </span>
            <strong>{data.daily_action_reason || data.no_buy_reason || '依今日位置觀察'}</strong>
            <span>{data.daily_action_identity || '未持有'} · 關鍵 {data.daily_key_price || '—'}</span>
          </div>
          <em>{data.daily_invalidation || '收盤確認後再更新正式訊號'}</em>
        </div>
      )}

      <DailyChecklist items={data.daily_checklist} />

      {/* 型態辨識 */}
      <PatternBadge pattern={data.pattern} />

      {/* 技術指標 */}
      <div className="panel-indicators">
        {data.close  != null && <span>收盤 <strong>{data.close}</strong></span>}
        {data.ma5    != null && <span>MA5 <strong>{data.ma5}</strong></span>}
        {data.ma20   != null && <span>MA20 <strong>{data.ma20}</strong></span>}
        {data.ma60   != null && <span>MA60 <strong>{data.ma60}</strong></span>}
        {data.rsi14  != null && <span>RSI14 <strong>{data.rsi14}</strong></span>}
        {data.vol_ratio != null && <span>量比 <strong>{data.vol_ratio}x</strong></span>}
      </div>

      <div className="price-plan-grid">
        <div className="price-plan-card entry">
          <div className="price-plan-label">建議進場區間</div>
          <div className="price-plan-value">
            {data.entry_price_low != null && data.entry_price_high != null
              ? `${fmtPrice(data.entry_price_low)} – ${fmtPrice(data.entry_price_high)}`
              : '暫不建議新進場'}
          </div>
        </div>
        <div className="price-plan-card stop">
          <div className="price-plan-label">停損 / 出場價</div>
          <div className="price-plan-value">{fmtPrice(data.stop_price)}</div>
          {data.risk_pct != null && <div className="price-plan-sub">風險 {data.risk_pct}%</div>}
        </div>
        <div className="price-plan-card target">
          <div className="price-plan-label">停利目標</div>
          <div className="price-plan-value">{fmtPrice(data.target_price)}</div>
          {data.reward_pct != null && <div className="price-plan-sub">空間 {data.reward_pct}%</div>}
        </div>
        <div className="price-plan-card rr">
          <div className="price-plan-label">風險報酬比</div>
          <div className="price-plan-value">{data.reward_risk_ratio ?? '—'}</div>
        </div>
      </div>
      {data.price_plan_note && (
        <div className="price-plan-note">{data.price_plan_note}</div>
      )}
      <div className="position-plan-note">
        <strong>建議倉位 {data.position_size_pct}%</strong>
        <span>{data.position_size_note}</span>
      </div>

      {/* 進場理由 */}
      {data.reasons.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-title">進場條件</div>
          <ul className="panel-list">
            {data.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* 不進場理由 */}
      {data.no_buy_reason && (
        <div className="panel-section">
          <div className="panel-section-title">未進場原因</div>
          <p className="panel-no-buy">{data.no_buy_reason}</p>
        </div>
      )}

      {/* 風險提示 */}
      {data.risk_notes.length > 0 && (
        <div className="panel-section panel-risk">
          <div className="panel-section-title">風險提示</div>
          <ul className="panel-list">
            {data.risk_notes.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* 資料不足提示 */}
      {!data.data_ok && (
        <div className="panel-section panel-risk">
          <p>{data.data_missing_reason}</p>
        </div>
      )}
    </div>
  )
}
