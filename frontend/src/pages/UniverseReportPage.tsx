import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import DailyChecklist from '../components/DailyChecklist'
import type { DataStatus, DecisionJournalCreate, DecisionJournalDecision, DecisionJournalEntry, SignalsStatus, SignalsSummary, UniverseReportItem } from '../types'
import {
  filterReport,
  hasOldWangTag,
  hasSteadyMomentum,
  resolveMarket,
  type MarketFilter,
  type PlanFilter,
  type HoldingFilter,
  type SignalFilter,
} from '../utils/reportFilter'

// ── 常數：7 狀態中文標籤 / badge class ──────────────────────────────────────

const SIG_LABEL: Record<string, string> = {
  entry_confirmed:     '確認入場',
  ready_to_enter:      '準備入場',
  watchlist:           '觀察中',
  hold:                '持股中',
  take_profit_warning: '停利觀察',
  exit_warning:        '出場警示',
  invalidated:         '趨勢失效',
  DATA_MISSING:        '資料不足',
}

const SIG_CLASS: Record<string, string> = {
  entry_confirmed:     'signal-badge sig-buy-strong',
  ready_to_enter:      'signal-badge sig-buy',
  watchlist:           'signal-badge sig-watch',
  hold:                'signal-badge sig-hold',
  take_profit_warning: 'signal-badge sig-caution',
  exit_warning:        'signal-badge sig-sell',
  invalidated:         'signal-badge sig-sell',
  DATA_MISSING:        'signal-badge sig-na',
}

const ALL_SIG_FILTERS: SignalFilter[] = [
  'all',
  'entry_confirmed',
  'ready_to_enter',
  'watchlist',
  'hold',
  'take_profit_warning',
  'exit_warning',
  'invalidated',
  'DATA_MISSING',
]

const TREND_ICON = (t: string, color: boolean) => {
  if (t === 'up')   return <span style={{ color: color ? '#c62828' : undefined }}>↑</span>
  if (t === 'down') return <span style={{ color: color ? '#2e7d32' : undefined }}>↓</span>
  return <span style={{ color: '#bbb' }}>—</span>
}

const PATTERN_LABEL: Record<string, string> = {
  w_bottom: 'W底',
  m_top: 'M頂',
  head_and_shoulders_bottom: '頭肩底',
}
const PATTERN_STATUS_LABEL: Record<string, string> = {
  confirmed: '確認', forming: '形成中', failed: '失效',
}

const fmtPrice = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

const fmtPct = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

const pctFromClose = (close?: number | null, target?: number | null) => {
  if (close == null || target == null || Number.isNaN(close) || Number.isNaN(target) || close === 0) return null
  return (target - close) / close * 100
}

const fmtTime = (value?: string | null) =>
  value ? value.slice(0, 16).replace('T', ' ') : '—'

const fmtDate = (value?: string | null) =>
  value ? value.slice(0, 10) : '—'

const todayInputValue = () => {
  const today = new Date()
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset())
  return today.toISOString().slice(0, 10)
}

const decisionActionToJournal = (action: string, item?: UniverseReportItem): DecisionJournalDecision => {
  const held = item ? isHeld(item) : false
  if (action === 'enter') return 'buy'
  if (action === 'reduce') return held ? 'reduce' : 'skip'
  if (action === 'exit') return held ? 'sell' : 'skip'
  if (action === 'hold') return 'hold'
  if (action === 'avoid') return 'skip'
  return 'watch'
}

const csvEscape = (value: unknown) => {
  const text = value == null ? '' : String(value)
  return `"${text.replace(/"/g, '""')}"`
}

const downloadTextFile = (filename: string, text: string, type = 'text/csv;charset=utf-8') => {
  const blob = new Blob([text], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

type DecisionAction =
  | 'all'
  | 'enter'
  | 'wait_pullback'
  | 'hold'
  | 'reduce'
  | 'exit'
  | 'avoid'
  | 'long_watch'

type ReportSortMode =
  | 'daily_priority'
  | 'score_desc'
  | 'reward_risk_desc'
  | 'entry_near'
  | 'target_near'

type PricePositionFilter =
  | 'all'
  | 'in_entry_range'
  | 'below_entry_range'
  | 'above_entry_range'
  | 'has_price_plan'

type JournalStatusFilter = 'all' | 'unrecorded' | 'recorded'

interface DailyDecision {
  action: Exclude<DecisionAction, 'all'>
  label: string
  cls: string
  identity: '已持有' | '未持有'
  oneLine: string
  keyPrice: string
  invalidation: string
  priority: number
}

const DECISION_LABEL: Record<DecisionAction, string> = {
  all: '全部動作',
  enter: '可小試',
  wait_pullback: '等回測',
  hold: '續抱',
  reduce: '減碼觀察',
  exit: '出場處理',
  avoid: '暫不碰',
  long_watch: '長期觀察',
}

const REPORT_SORT_LABEL: Record<ReportSortMode, string> = {
  daily_priority: '今日優先',
  score_desc: '分數最高',
  reward_risk_desc: 'R/R 最好',
  entry_near: '離進場最近',
  target_near: '離目標最近',
}

const PRICE_POSITION_LABEL: Record<PricePositionFilter, string> = {
  all: '全部位置',
  in_entry_range: '進場區間內',
  below_entry_range: '低於進場區',
  above_entry_range: '高於進場區',
  has_price_plan: '有完整價格計畫',
}

const JOURNAL_STATUS_LABEL: Record<JournalStatusFilter, string> = {
  all: '全部復盤',
  unrecorded: '尚未記錄',
  recorded: '已記錄',
}

const MARKET_FILTER_LABEL: Record<string, string> = {
  all: '全部市場',
  TWSE: 'TWSE 上市',
  TPEX: 'TPEX 上櫃',
  ETF: 'ETF',
}

const PLAN_FILTER_LABEL: Record<string, string> = {
  all: '全部方案',
  confluence: '雙重共振',
  steady_momentum: '穩健動能',
  old_wang: '老王短波段',
  no_entry: '暫不進場',
}

const HOLDING_FILTER_LABEL: Record<string, string> = {
  all: '全部持股狀態',
  holding: '目前持股',
  not_holding: '非持股',
}

const DECISION_ORDER: Exclude<DecisionAction, 'all'>[] = [
  'exit',
  'reduce',
  'enter',
  'wait_pullback',
  'hold',
  'long_watch',
  'avoid',
]

const DECISION_URGENCY: Record<Exclude<DecisionAction, 'all'>, number> = {
  exit: 0,
  reduce: 1,
  enter: 2,
  wait_pullback: 3,
  hold: 4,
  long_watch: 5,
  avoid: 6,
}

const ACTIONABLE_REPORT_JOURNAL_ACTIONS = new Set<Exclude<DecisionAction, 'all'>>([
  'enter',
  'wait_pullback',
  'reduce',
  'exit',
])

const isHeld = (item: UniverseReportItem) => (item.holding_shares ?? 0) > 0

const getEntryDistance = (item: UniverseReportItem) => {
  const close = item.close
  const low = item.entry_price_low
  const high = item.entry_price_high
  if (close == null || low == null || high == null) return null
  if (close >= low && close <= high) {
    return { label: '區間內', cls: 'price-distance-ok' }
  }
  if (close < low) {
    return { label: `距下緣 ${fmtPct(pctFromClose(close, low))}`, cls: 'price-distance-watch' }
  }
  return { label: `高於上緣 ${fmtPct((close - high) / high * 100)}`, cls: 'price-distance-risk' }
}

const getEntryPosition = (item: UniverseReportItem): Exclude<PricePositionFilter, 'all' | 'has_price_plan'> | null => {
  const close = item.close
  const low = item.entry_price_low
  const high = item.entry_price_high
  if (close == null || low == null || high == null) return null
  if (close >= low && close <= high) return 'in_entry_range'
  if (close < low) return 'below_entry_range'
  return 'above_entry_range'
}

const hasCompletePricePlan = (item: UniverseReportItem) => (
  item.entry_price_low != null &&
  item.entry_price_high != null &&
  item.stop_price != null &&
  item.target_price != null
)

const getStopDistance = (item: UniverseReportItem) => {
  const distance = pctFromClose(item.close, item.stop_price)
  if (distance == null) return null
  return {
    label: `距停損 ${fmtPct(distance)}`,
    cls: distance > -3 ? 'price-distance-risk' : distance > -8 ? 'price-distance-watch' : 'price-distance-ok',
  }
}

const getTargetDistance = (item: UniverseReportItem) => {
  const distance = pctFromClose(item.close, item.target_price)
  if (distance == null) return null
  return {
    label: `距目標 ${fmtPct(distance)}`,
    cls: distance <= 0 ? 'price-distance-risk' : distance < 5 ? 'price-distance-watch' : 'price-distance-ok',
  }
}

const getEntryRangeDistancePct = (item: UniverseReportItem) => {
  const close = item.close
  const low = item.entry_price_low
  const high = item.entry_price_high
  if (close == null || low == null || high == null || close === 0) return Number.POSITIVE_INFINITY
  if (close >= low && close <= high) return 0
  if (close < low) return Math.abs((low - close) / close * 100)
  return Math.abs((close - high) / high * 100)
}

const getTargetDistancePct = (item: UniverseReportItem) => {
  const distance = pctFromClose(item.close, item.target_price)
  if (distance == null) return Number.POSITIVE_INFINITY
  return Math.abs(distance)
}

const getKeySupport = (item: UniverseReportItem) => {
  if (item.old_wang_volume_low_price != null) return `爆量低 ${fmtPrice(item.old_wang_volume_low_price)}`
  if (item.old_wang_gap_support != null) return `缺口 ${fmtPrice(item.old_wang_gap_support)}`
  if (item.ma10 != null) return `MA10 ${fmtPrice(item.ma10)}`
  if (item.ma20 != null) return `MA20 ${fmtPrice(item.ma20)}`
  if (item.stop_price != null) return `停損 ${fmtPrice(item.stop_price)}`
  return '—'
}

const getDailyDecision = (item: UniverseReportItem): DailyDecision => {
  if (
    item.daily_action &&
    item.daily_action !== 'all' &&
    DECISION_ORDER.includes(item.daily_action as Exclude<DecisionAction, 'all'>)
  ) {
    return {
      action: item.daily_action as Exclude<DecisionAction, 'all'>,
      label: item.daily_action_label || DECISION_LABEL[item.daily_action as DecisionAction] || item.daily_action,
      cls: {
        enter: 'decision-enter',
        wait_pullback: 'decision-watch',
        hold: 'decision-hold',
        reduce: 'decision-caution',
        exit: 'decision-risk',
        avoid: 'decision-muted',
        long_watch: 'decision-long',
      }[item.daily_action] || 'decision-muted',
      identity: item.daily_action_identity === '已持有' ? '已持有' : '未持有',
      oneLine: item.daily_action_reason || item.no_buy_reason || '條件未完整成立',
      keyPrice: item.daily_key_price || getKeySupport(item),
      invalidation: item.daily_invalidation || '等待重新轉強或出現買點',
      priority: item.daily_priority ?? 40,
    }
  }

  const held = isHeld(item)
  const oldWang = hasOldWangTag(item)
  const steadyMomentum = hasSteadyMomentum(item)
  const hot = item.rsi14 != null && item.rsi14 > 75
  const keySupport = getKeySupport(item)
  const stop = item.stop_price != null ? fmtPrice(item.stop_price) : keySupport

  if (!item.data_ok || item.internal_signal === 'DATA_MISSING') {
    return {
      action: 'avoid',
      label: '資料不足',
      cls: 'decision-muted',
      identity: held ? '已持有' : '未持有',
      oneLine: '資料不足，先不做交易判斷',
      keyPrice: '—',
      invalidation: '補齊資料後重算',
      priority: 80,
    }
  }

  if (item.internal_signal === 'invalidated' || item.internal_signal === 'exit_warning') {
    return {
      action: 'exit',
      label: held ? '出場處理' : '暫不進場',
      cls: 'decision-risk',
      identity: held ? '已持有' : '未持有',
      oneLine: item.no_buy_reason || '趨勢或支撐已破壞',
      keyPrice: stop,
      invalidation: '重新站回 MA20/MA60 後再評估',
      priority: 100,
    }
  }

  if (held) {
    if (item.internal_signal === 'take_profit_warning' || (hot && item.old_wang_support_state !== 'short_stop_trend_intact')) {
      return {
        action: 'reduce',
        label: '減碼觀察',
        cls: 'decision-caution',
        identity: '已持有',
        oneLine: hot ? '短線過熱，跌破 5/10 再減碼' : item.no_buy_reason || '接近壓力區，先控風險',
        keyPrice: keySupport,
        invalidation: `跌破 ${keySupport}`,
        priority: 95,
      }
    }
    return {
      action: 'hold',
      label: '續抱',
      cls: 'decision-hold',
      identity: '已持有',
      oneLine: oldWang ? '仍守老王關鍵支撐，不預設高點' : '長線未轉弱，依停損續抱',
      keyPrice: keySupport,
      invalidation: `跌破 ${keySupport}`,
      priority: 70,
    }
  }

  if (steadyMomentum && oldWang && !hot) {
    return {
      action: 'enter',
      label: '可小試',
      cls: 'decision-enter',
      identity: '未持有',
      oneLine: '穩健動能與老王旗標共振，可依區間小量',
      keyPrice: item.entry_price_low != null && item.entry_price_high != null
        ? `${fmtPrice(item.entry_price_low)}–${fmtPrice(item.entry_price_high)}`
        : keySupport,
      invalidation: `跌破 ${stop}`,
      priority: 90,
    }
  }

  if (steadyMomentum) {
    return {
      action: 'enter',
      label: '可小試',
      cls: 'decision-enter',
      identity: '未持有',
      oneLine: steadyMomentum
        ? '穩健動能成立，可分批規劃'
        : item.entry_type === 'breakout' ? '突破成立但仍需控量' : '進場條件成立，可分批',
      keyPrice: item.entry_price_low != null && item.entry_price_high != null
        ? `${fmtPrice(item.entry_price_low)}–${fmtPrice(item.entry_price_high)}`
        : keySupport,
      invalidation: `跌破 ${stop}`,
      priority: 86,
    }
  }

  if (oldWang) {
    return {
      action: 'wait_pullback',
      label: '等回測',
      cls: 'decision-watch',
      identity: '未持有',
      oneLine: hot ? '老王旗標成立但短線過熱，不追高' : '老王旗標成立，等 5/10 或支撐確認',
      keyPrice: keySupport,
      invalidation: `跌破 ${keySupport}`,
      priority: 82,
    }
  }

  return {
    action: 'avoid',
    label: item.internal_signal === 'watchlist' ? '先觀察' : '暫不碰',
    cls: 'decision-muted',
    identity: '未持有',
    oneLine: item.no_buy_reason || '條件未完整成立',
    keyPrice: keySupport,
    invalidation: '等待重新轉強或出現買點',
    priority: 40,
  }
}

const getRecommendedPlan = (item: UniverseReportItem) => {
  const oldWang = hasOldWangTag(item)
  const steadyMomentum = hasSteadyMomentum(item)

  if (!item.data_ok || item.internal_signal === 'DATA_MISSING') {
    return {
      title: '無方案',
      cls: 'plan-badge plan-muted',
      advice: '資料不足',
      detail: '先補資料',
    }
  }

  if (item.old_wang_previous_high_risk) {
    return {
      title: '老王風險',
      cls: 'plan-badge plan-risk',
      advice: '不建議進場',
      detail: '5/10/20/60 全破',
    }
  }

  if (steadyMomentum && oldWang) {
    return {
      title: '雙重共振',
      cls: 'plan-badge plan-strong',
      advice: item.entry_type === 'breakout' ? '可小量試單' : '等區間分批',
      detail: item.old_wang_support_state === 'short_stop_trend_intact'
        ? '穩健動能 + 老王均線支撐'
        : '穩健動能 + 老王 tag',
    }
  }

  if (oldWang) {
    return {
      title: '老王觀察',
      cls: 'plan-badge plan-wang',
      advice: '不追高，等 5/10',
      detail: item.old_wang_volume_low_support
        ? `守大量低點 ${fmtPrice(item.old_wang_volume_low_price)}`
        : item.old_wang_gap_type === 'gap_up'
          ? `守跳空支撐 ${fmtPrice(item.old_wang_gap_support)}`
          : '短線止跌再分批',
    }
  }

  if (steadyMomentum) {
    return {
      title: '穩健動能',
      cls: 'plan-badge plan-core',
      advice: item.entry_type === 'breakout' ? '可小量試單' : '等區間分批',
      detail: item.steady_momentum_reason || item.price_plan_note || '依進場區間執行',
    }
  }

  if (item.internal_signal === 'take_profit_warning') {
    return {
      title: '停利觀察',
      cls: 'plan-badge plan-watch',
      advice: '不追價',
      detail: item.no_buy_reason || '等待回測或短均線轉弱',
    }
  }

  if (['exit_warning', 'invalidated'].includes(item.internal_signal)) {
    return {
      title: '無方案',
      cls: 'plan-badge plan-risk',
      advice: '暫不進場',
      detail: item.no_buy_reason || '風險訊號',
    }
  }

  return {
    title: '觀察方案',
    cls: 'plan-badge plan-watch',
    advice: '等條件成立',
    detail: item.no_buy_reason || item.price_plan_note || '尚未到進場點',
  }
}

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  onNavigateAnalysis: (code: string) => void
  initialJournalFilter?: JournalStatusFilter
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function UniverseReportPage({ onNavigateAnalysis, initialJournalFilter = 'all' }: Props) {
  const [items, setItems]     = useState<UniverseReportItem[] | null>(null)
  const [summary, setSummary] = useState<SignalsSummary | null>(null)
  const [signalStatus, setSignalStatus] = useState<SignalsStatus | null>(null)
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [runningSignals, setRunningSignals] = useState(false)
  const [updatingData, setUpdatingData] = useState(false)

  const [sigFilter, setSigFilter] = useState<SignalFilter>('all')
  const [mktFilter, setMktFilter] = useState<MarketFilter>('all')
  const [planFilter, setPlanFilter] = useState<PlanFilter>('all')
  const [holdingFilter, setHoldingFilter] = useState<HoldingFilter>('all')
  const [decisionFilter, setDecisionFilter] = useState<DecisionAction>('all')
  const [pricePositionFilter, setPricePositionFilter] = useState<PricePositionFilter>('all')
  const [journalStatusFilter, setJournalStatusFilter] = useState<JournalStatusFilter>(initialJournalFilter)
  const [sortMode, setSortMode] = useState<ReportSortMode>('daily_priority')
  const [keyword, setKeyword]     = useState('')
  const [expandedCode, setExpandedCode] = useState<string | null>(null)
  const [copiedSnapshot, setCopiedSnapshot] = useState(false)
  const [savingJournalCode, setSavingJournalCode] = useState<string | null>(null)
  const [bulkSavingJournals, setBulkSavingJournals] = useState(false)
  const [journalMessage, setJournalMessage] = useState<string | null>(null)
  const [journalEntries, setJournalEntries] = useState<DecisionJournalEntry[]>([])
  const universeFile = signalStatus?.out_files.universe_report_csv

  const reportAsOf = summary?.as_of ?? dataStatus?.last_data_as_of ?? null

  const loadReport = useCallback(() => {
    setError(null)
    return Promise.all([
      api.getUniverseReportOrNull(),
      api.getSummaryOrNull(),
      api.getSignalsStatus(),
      api.getDataStatus(),
    ]).then(([report, sum, status, data]) => {
      setItems(report ?? [])
      setSummary(sum)
      setSignalStatus(status)
      setDataStatus(data)
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    loadReport()
      .catch(err => {
        if (!cancelled) setError(String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [loadReport])

  useEffect(() => {
    setJournalStatusFilter(initialJournalFilter)
  }, [initialJournalFilter])

  useEffect(() => {
    if (signalStatus?.run_status !== 'running') return

    let cancelled = false
    const timer = window.setInterval(() => {
      api.getSignalsStatus()
        .then(status => {
          if (cancelled) return
          setSignalStatus(status)
          if (status.run_status !== 'running') {
            window.clearInterval(timer)
            loadReport().catch(err => {
              if (!cancelled) setError(String(err))
            })
          }
        })
        .catch(err => {
          if (!cancelled) setError(String(err))
        })
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [signalStatus?.run_status, loadReport])

  useEffect(() => {
    if (dataStatus?.last_run_status !== 'running') {
      setUpdatingData(false)
      return
    }

    let cancelled = false
    const timer = window.setInterval(() => {
      api.getDataStatus()
        .then(status => {
          if (cancelled) return
          setDataStatus(status)
          if (status.last_run_status !== 'running') {
            window.clearInterval(timer)
            loadReport().catch(err => {
              if (!cancelled) setError(String(err))
            })
          }
        })
        .catch(err => {
          if (!cancelled) setError(err instanceof Error ? err.message : String(err))
        })
    }, 3000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [dataStatus?.last_run_status, loadReport])

  useEffect(() => {
    if (!reportAsOf) {
      setJournalEntries([])
      return
    }
    let cancelled = false
    api.getDecisionJournal(500, { date: reportAsOf })
      .then(entries => {
        if (!cancelled) setJournalEntries(entries)
      })
      .catch(() => {
        if (!cancelled) setJournalEntries([])
      })
    return () => { cancelled = true }
  }, [reportAsOf])

  const handleUpdateData = async () => {
    if (updatingData || dataStatus?.last_run_status === 'running') return
    setError(null)
    setUpdatingData(true)
    try {
      await api.triggerUpdateNow()
      setDataStatus(prev => prev
        ? { ...prev, last_run_status: 'running', last_run_started_at: new Date().toISOString().slice(0, 19) }
        : prev
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : '觸發更新失敗'
      if (msg.includes('已在執行中') || msg.includes('running')) {
        setDataStatus(prev => prev ? { ...prev, last_run_status: 'running' } : prev)
      } else {
        setError(msg)
        setUpdatingData(false)
      }
    }
  }

  const handleRunSignals = async () => {
    setError(null)
    setRunningSignals(true)
    try {
      await api.runSignals()
      const [status, data] = await Promise.all([
        api.getSignalsStatus(),
        api.getDataStatus(),
      ])
      setSignalStatus(status)
      setDataStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunningSignals(false)
    }
  }

  const resetReportFilters = () => {
    setSigFilter('all')
    setMktFilter('all')
    setPlanFilter('all')
    setHoldingFilter('all')
    setDecisionFilter('all')
    setPricePositionFilter('all')
    setJournalStatusFilter('all')
    setSortMode('daily_priority')
    setKeyword('')
  }

  const showDecisionFilter = (action: DecisionAction) => {
    setDecisionFilter(prev => (prev === action ? 'all' : action))
  }

  const renderTrustNote = () => dataStatus ? (
    <div
      className={`report-trust-note ${
        dataStatus.outputs_lag_raw_data || dataStatus.is_stale ? 'report-trust-warning' : ''
      }`}
    >
      <div>
        <strong>報表可信度</strong>
        <span>
          價格基準：{dataStatus.price_basis_label ?? '最新收盤價'}；
          資料日 <strong>{fmtDate(dataStatus.last_data_as_of)}</strong>
          {dataStatus.raw_ohlcv_as_of && (
            <> ／ OHLCV <strong>{fmtDate(dataStatus.raw_ohlcv_as_of)}</strong></>
          )}
        </span>
        <em>
          {dataStatus.outputs_lag_raw_data
            ? dataStatus.raw_data_warning ?? '原始日線比報表新，需重新產生訊號。'
            : dataStatus.is_stale
              ? `資料已 ${dataStatus.stale_days != null ? `${dataStatus.stale_days} 天` : '數天'}未更新，今天決策需先更新資料。`
              : dataStatus.price_basis_note ?? '報表使用最新收盤價，不是盤中即時市價。'}
        </em>
      </div>
      {dataStatus.is_stale ? (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleUpdateData}
          disabled={updatingData || dataStatus.last_run_status === 'running'}
        >
          {updatingData || dataStatus.last_run_status === 'running' ? '更新中…' : '更新資料'}
        </button>
      ) : dataStatus.outputs_lag_raw_data ? (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleRunSignals}
          disabled={runningSignals || signalStatus?.run_status === 'running'}
        >
          {runningSignals || signalStatus?.run_status === 'running' ? '啟動中…' : '重新產生訊號'}
        </button>
      ) : null}
    </div>
  ) : null

  const baseFiltered = useMemo(() => {
    const base = filterReport(items ?? [], sigFilter, mktFilter, planFilter, holdingFilter, keyword)
    if (pricePositionFilter === 'all') return base
    if (pricePositionFilter === 'has_price_plan') return base.filter(hasCompletePricePlan)
    return base.filter(item => getEntryPosition(item) === pricePositionFilter)
  }, [items, sigFilter, mktFilter, planFilter, holdingFilter, keyword, pricePositionFilter])

  const pricePositionBase = useMemo(() => (
    filterReport(items ?? [], sigFilter, mktFilter, planFilter, holdingFilter, keyword)
  ), [items, sigFilter, mktFilter, planFilter, holdingFilter, keyword])

  const pricePositionCounts = useMemo(() => {
    const counts: Record<Exclude<PricePositionFilter, 'all'>, number> = {
      in_entry_range: 0,
      below_entry_range: 0,
      above_entry_range: 0,
      has_price_plan: 0,
    }
    for (const item of pricePositionBase) {
      if (hasCompletePricePlan(item)) counts.has_price_plan += 1
      const position = getEntryPosition(item)
      if (position) counts[position] += 1
    }
    return counts
  }, [pricePositionBase])

  const journalRecordedCodes = useMemo(() => (
    new Set(journalEntries.filter(entry => entry.source === 'universe_report').map(entry => entry.code))
  ), [journalEntries])

  const journalProgress = useMemo(() => {
    let actionableCount = 0
    let recordedActionableCount = 0
    let recordedAnyCount = 0

    for (const item of baseFiltered) {
      const recorded = journalRecordedCodes.has(item.code)
      const action = getDailyDecision(item).action
      const actionable = ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(action)
      if (recorded) recordedAnyCount += 1
      if (!actionable) continue
      actionableCount += 1
      if (recorded) recordedActionableCount += 1
    }

    return {
      actionableCount,
      recordedActionableCount,
      missingActionableCount: Math.max(actionableCount - recordedActionableCount, 0),
      recordedAnyCount,
    }
  }, [baseFiltered, journalRecordedCodes])

  const unrecordedJournalRows = useMemo(() => (
    baseFiltered
      .map(item => ({
        item,
        decision: getDailyDecision(item),
        plan: getRecommendedPlan(item),
      }))
      .filter(row => ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(row.decision.action) && !journalRecordedCodes.has(row.item.code))
      .sort((a, b) => (
        DECISION_URGENCY[a.decision.action] - DECISION_URGENCY[b.decision.action]
        || b.decision.priority - a.decision.priority
        || (b.item.score ?? 0) - (a.item.score ?? 0)
      ))
  ), [baseFiltered, journalRecordedCodes])

  const filtered = useMemo(() => {
    const actionScoped = decisionFilter === 'all'
      ? baseFiltered
      : baseFiltered.filter(item => getDailyDecision(item).action === decisionFilter)
    const scoped = actionScoped.filter(item => {
      if (journalStatusFilter === 'all') return true
      const action = getDailyDecision(item).action
      const recorded = journalRecordedCodes.has(item.code)
      if (journalStatusFilter === 'recorded') return recorded
      return ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(action) && !recorded
    })
    return [...scoped].sort((a, b) => {
      const da = getDailyDecision(a)
      const db = getDailyDecision(b)
      const dailyOrder = DECISION_URGENCY[da.action] - DECISION_URGENCY[db.action]
        || db.priority - da.priority
        || (b.score ?? 0) - (a.score ?? 0)
      if (sortMode === 'score_desc') {
        return (b.score ?? -1) - (a.score ?? -1) || dailyOrder
      }
      if (sortMode === 'reward_risk_desc') {
        return (b.reward_risk_ratio ?? -1) - (a.reward_risk_ratio ?? -1) || dailyOrder
      }
      if (sortMode === 'entry_near') {
        return getEntryRangeDistancePct(a) - getEntryRangeDistancePct(b) || dailyOrder
      }
      if (sortMode === 'target_near') {
        return getTargetDistancePct(a) - getTargetDistancePct(b) || dailyOrder
      }
      return dailyOrder
    })
  }, [baseFiltered, decisionFilter, journalRecordedCodes, journalStatusFilter, sortMode])

  const decisionGroups = useMemo(() => {
    return DECISION_ORDER.map(action => {
      const grouped = baseFiltered
        .map(item => ({ item, decision: getDailyDecision(item) }))
        .filter(row => row.decision.action === action)
        .sort((a, b) => b.decision.priority - a.decision.priority || (b.item.score ?? 0) - (a.item.score ?? 0))
      return { action, label: DECISION_LABEL[action], rows: grouped }
    }).filter(group => group.rows.length > 0)
  }, [baseFiltered])

  const topPriorityRows = useMemo(() => {
    const priorityActions = new Set<Exclude<DecisionAction, 'all'>>(['exit', 'reduce', 'enter', 'wait_pullback'])
    return filtered
      .map(item => ({
        item,
        decision: getDailyDecision(item),
        plan: getRecommendedPlan(item),
      }))
      .filter(row => priorityActions.has(row.decision.action))
      .sort((a, b) => (
        DECISION_URGENCY[a.decision.action] - DECISION_URGENCY[b.decision.action]
        || b.decision.priority - a.decision.priority
        || (b.item.score ?? 0) - (a.item.score ?? 0)
      ))
      .slice(0, 8)
  }, [filtered])

  const stats = useMemo(() => {
    if (!items?.length) return null
    const bySignal: Record<string, number> = {}
    const byMarket: Record<string, number> = { TWSE: 0, TPEX: 0, ETF: 0 }
    for (const item of baseFiltered) {
      const sig = item.internal_signal
      bySignal[sig] = (bySignal[sig] ?? 0) + 1
      const mkt = resolveMarket(item)
      byMarket[mkt] = (byMarket[mkt] ?? 0) + 1
    }
    return { bySignal, byMarket, total: baseFiltered.length, universeTotal: items.length }
  }, [items, baseFiltered])

  const reportSummary = useMemo(() => {
    if (!items?.length) return null
    const byDecision = DECISION_ORDER.reduce((acc, action) => {
      acc[action] = 0
      return acc
    }, {} as Record<Exclude<DecisionAction, 'all'>, number>)
    const missingItems: UniverseReportItem[] = []
    let dataOkCount = 0
    let entryRangeCount = 0
    let exitPlanCount = 0
    let heldCount = 0

    for (const item of baseFiltered) {
      const decision = getDailyDecision(item).action
      byDecision[decision] += 1
      if (item.data_ok && item.internal_signal !== 'DATA_MISSING') dataOkCount += 1
      else missingItems.push(item)
      if (item.entry_price_low != null && item.entry_price_high != null) entryRangeCount += 1
      if (item.stop_price != null || item.target_price != null) exitPlanCount += 1
      if (isHeld(item)) heldCount += 1
    }

    return {
      total: baseFiltered.length,
      universeTotal: items.length,
      dataOkCount,
      dataMissingCount: missingItems.length,
      dataOkPct: baseFiltered.length ? dataOkCount / baseFiltered.length * 100 : 0,
      byDecision,
      entryRangeCount,
      exitPlanCount,
      heldCount,
      missingItems: missingItems.slice(0, 6),
    }
  }, [items, baseFiltered])

  const activeFilterLabels = useMemo(() => {
    const labels: Array<{ key: string; label: string; clear: () => void }> = []
    if (sigFilter !== 'all') labels.push({
      key: 'sig',
      label: `訊號：${SIG_LABEL[sigFilter] ?? sigFilter}`,
      clear: () => setSigFilter('all'),
    })
    if (mktFilter !== 'all') labels.push({
      key: 'market',
      label: `市場：${MARKET_FILTER_LABEL[mktFilter] ?? mktFilter}`,
      clear: () => setMktFilter('all'),
    })
    if (planFilter !== 'all') labels.push({
      key: 'plan',
      label: `方案：${PLAN_FILTER_LABEL[planFilter] ?? planFilter}`,
      clear: () => setPlanFilter('all'),
    })
    if (holdingFilter !== 'all') labels.push({
      key: 'holding',
      label: `持股：${HOLDING_FILTER_LABEL[holdingFilter] ?? holdingFilter}`,
      clear: () => setHoldingFilter('all'),
    })
    if (decisionFilter !== 'all') labels.push({
      key: 'decision',
      label: `今日動作：${DECISION_LABEL[decisionFilter] ?? decisionFilter}`,
      clear: () => setDecisionFilter('all'),
    })
    if (pricePositionFilter !== 'all') labels.push({
      key: 'price-position',
      label: `價格位置：${PRICE_POSITION_LABEL[pricePositionFilter]}`,
      clear: () => setPricePositionFilter('all'),
    })
    if (journalStatusFilter !== 'all') labels.push({
      key: 'journal-status',
      label: `復盤：${JOURNAL_STATUS_LABEL[journalStatusFilter]}`,
      clear: () => setJournalStatusFilter('all'),
    })
    if (sortMode !== 'daily_priority') labels.push({
      key: 'sort',
      label: `排序：${REPORT_SORT_LABEL[sortMode]}`,
      clear: () => setSortMode('daily_priority'),
    })
    if (keyword.trim()) labels.push({
      key: 'keyword',
      label: `關鍵字：${keyword.trim()}`,
      clear: () => setKeyword(''),
    })
    return labels
  }, [sigFilter, mktFilter, planFilter, holdingFilter, decisionFilter, pricePositionFilter, journalStatusFilter, sortMode, keyword])

  const reportSnapshot = useMemo(() => {
    const asOf = summary?.as_of ?? dataStatus?.last_data_as_of ?? '—'
    const filters = activeFilterLabels
      .filter(filter => filter.key !== 'sort')
      .map(filter => filter.label)
      .join(' / ') || '未套用篩選'
    const topLines = filtered.slice(0, 3).map((item, index) => {
      const decision = getDailyDecision(item)
      const plan = getRecommendedPlan(item)
      const entryDistance = getEntryDistance(item)
      const stopDistance = getStopDistance(item)
      const targetDistance = getTargetDistance(item)
      const actionable = ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(decision.action)
      const recorded = journalRecordedCodes.has(item.code)
      return [
        `${index + 1}. ${item.name}${item.code}`,
        decision.label,
        plan.title,
        actionable ? (recorded ? '已復盤' : '待復盤') : '非可行動',
        `收盤 ${fmtPrice(item.close)}`,
        entryDistance?.label,
        stopDistance?.label,
        targetDistance?.label,
      ].filter(Boolean).join(' / ')
    })
    return [
      `候選股篩選報告 ${asOf}`,
      `顯示 ${filtered.length}/${items?.length ?? 0} 檔`,
      `排序：${REPORT_SORT_LABEL[sortMode]}`,
      `篩選：${filters}`,
      `復盤進度：可行動 ${journalProgress.actionableCount} / 已記錄 ${journalProgress.recordedActionableCount} / 尚未記錄 ${journalProgress.missingActionableCount}`,
      topLines.length ? `Top3:\n${topLines.join('\n')}` : 'Top3：無',
    ].join('\n')
  }, [activeFilterLabels, dataStatus?.last_data_as_of, filtered, items?.length, journalProgress, journalRecordedCodes, sortMode, summary?.as_of])

  const snapshotTopRows = useMemo(() => (
    filtered.slice(0, 3).map(item => ({
      item,
      decision: getDailyDecision(item),
      plan: getRecommendedPlan(item),
      entryDistance: getEntryDistance(item),
      stopDistance: getStopDistance(item),
      targetDistance: getTargetDistance(item),
    }))
  ), [filtered])

  const handleCopySnapshot = async () => {
    try {
      await navigator.clipboard.writeText(reportSnapshot)
      setCopiedSnapshot(true)
      window.setTimeout(() => setCopiedSnapshot(false), 1600)
    } catch {
      const asOf = summary?.as_of ?? dataStatus?.last_data_as_of ?? fmtDate(new Date().toISOString())
      downloadTextFile(`universe_report_snapshot_${asOf}.txt`, reportSnapshot, 'text/plain;charset=utf-8')
    }
  }

  const handleCopyUnrecordedJournalList = async () => {
    const asOf = summary?.as_of ?? dataStatus?.last_data_as_of ?? '—'
    const lines = unrecordedJournalRows.map(({ item, decision, plan }, index) => [
      `${index + 1}. ${item.name}${item.code}`,
      decision.label,
      plan.title,
      `關鍵 ${decision.keyPrice}`,
      `失效 ${decision.invalidation}`,
      decision.oneLine,
    ].join(' / '))
    const text = [
      `候選股待補復盤 ${asOf}`,
      `尚未記錄 ${unrecordedJournalRows.length} 檔`,
      lines.length ? lines.join('\n') : '目前沒有待補復盤。',
    ].join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setJournalMessage(`已複製待補復盤清單 ${unrecordedJournalRows.length} 檔`)
      window.setTimeout(() => setJournalMessage(null), 2200)
    } catch {
      const filenameDate = summary?.as_of ?? dataStatus?.last_data_as_of ?? fmtDate(new Date().toISOString())
      downloadTextFile(`universe_report_unrecorded_${filenameDate}.txt`, text, 'text/plain;charset=utf-8')
    }
  }

  const buildJournalPayloadFromReport = (item: UniverseReportItem): DecisionJournalCreate => {
    const decision = getDailyDecision(item)
    const plan = getRecommendedPlan(item)
    const entryDistance = getEntryDistance(item)
    const stopDistance = getStopDistance(item)
    const targetDistance = getTargetDistance(item)
    const date = summary?.as_of ?? dataStatus?.last_data_as_of ?? todayInputValue()
    const reasonParts = [
      decision.oneLine,
      `${plan.title}：${plan.advice}`,
      item.price_plan_note,
      entryDistance?.label,
      stopDistance?.label,
      targetDistance?.label,
      item.no_buy_reason,
      item.risk_note,
    ].filter(Boolean)
    return {
      date,
      code: item.code,
      name: item.name,
      decision: decisionActionToJournal(decision.action, item),
      reason: reasonParts.join('；'),
      price: item.close ?? null,
      shares: item.holding_shares ?? null,
      key_price: decision.keyPrice || null,
      invalidation: decision.invalidation || null,
      source: 'universe_report',
    }
  }

  const handleCreateJournalFromReport = async (item: UniverseReportItem) => {
    if (savingJournalCode) return
    if (journalRecordedCodes.has(item.code)) {
      setJournalMessage(`${item.name} ${item.code} 在 ${reportAsOf ?? '目前資料日'} 已有決策日誌`)
      window.setTimeout(() => setJournalMessage(null), 2200)
      return
    }
    const payload = buildJournalPayloadFromReport(item)
    const ok = window.confirm(`將 ${item.name} ${item.code} 的目前報表判斷存成 ${payload.date} 決策日誌？這不會修改持倉或交易紀錄。`)
    if (!ok) return
    setSavingJournalCode(item.code)
    setJournalMessage(null)
    try {
      const created = await api.createDecisionJournalEntry(payload)
      setJournalEntries(prev => [
        created,
        ...prev.filter(entry => !(entry.date === created.date && entry.code === created.code && entry.source === created.source)),
      ])
      setJournalMessage(`已記錄 ${item.name} ${item.code} 的決策日誌`)
      window.setTimeout(() => setJournalMessage(null), 2200)
    } catch (err) {
      setJournalMessage(err instanceof Error ? err.message : '儲存決策日誌失敗')
    } finally {
      setSavingJournalCode(null)
    }
  }

  const handleBulkCreateUnrecordedJournals = async () => {
    if (bulkSavingJournals || unrecordedJournalRows.length === 0) return
    const rows = unrecordedJournalRows.slice(0, 6)
    const ok = window.confirm(`將前 ${rows.length} 檔待補復盤依候選股報表判斷批次存成決策日誌？這不會修改持倉或交易紀錄。`)
    if (!ok) return
    setBulkSavingJournals(true)
    setJournalMessage(null)
    const createdEntries: DecisionJournalEntry[] = []
    try {
      for (const row of rows) {
        const created = await api.createDecisionJournalEntry(buildJournalPayloadFromReport(row.item))
        createdEntries.push(created)
      }
      setJournalEntries(prev => [
        ...createdEntries.reverse(),
        ...prev.filter(entry => !createdEntries.some(created => (
          entry.date === created.date && entry.code === created.code && entry.source === created.source
        ))),
      ])
      setJournalMessage(`已批次記錄 ${createdEntries.length} 檔候選股復盤`)
      window.setTimeout(() => setJournalMessage(null), 2600)
    } catch (err) {
      setJournalMessage(err instanceof Error ? err.message : '批次儲存決策日誌失敗')
    } finally {
      setBulkSavingJournals(false)
    }
  }

  const handleDownloadFilteredCsv = () => {
    const headers = [
      '排序',
      '代號',
      '名稱',
      '市場',
      '今日動作',
      '身份',
      '今日理由',
      '觀察價',
      '失效條件',
      '推薦方案',
      '方案建議',
      '收盤',
      '進場下緣',
      '進場上緣',
      '進場位置',
      '停損',
      '距停損',
      '停利目標',
      '距目標',
      'R/R',
      '分數',
      '訊號',
      '不買理由',
      '風險提醒',
      '可行動復盤',
      '復盤狀態',
    ]
    const rows = filtered.map((item, index) => {
      const decision = getDailyDecision(item)
      const plan = getRecommendedPlan(item)
      const entryDistance = getEntryDistance(item)
      const stopDistance = getStopDistance(item)
      const targetDistance = getTargetDistance(item)
      const actionable = ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(decision.action)
      const recorded = journalRecordedCodes.has(item.code)
      return [
        index + 1,
        item.code,
        item.name,
        resolveMarket(item),
        decision.label,
        decision.identity,
        decision.oneLine,
        decision.keyPrice,
        decision.invalidation,
        plan.title,
        plan.advice,
        item.close ?? '',
        item.entry_price_low ?? '',
        item.entry_price_high ?? '',
        entryDistance?.label ?? '',
        item.stop_price ?? '',
        stopDistance?.label ?? '',
        item.target_price ?? '',
        targetDistance?.label ?? '',
        item.reward_risk_ratio ?? '',
        item.score ?? '',
        SIG_LABEL[item.internal_signal] ?? item.internal_signal,
        item.no_buy_reason ?? '',
        item.risk_note ?? '',
        actionable ? '是' : '否',
        actionable ? (recorded ? '已記錄' : '尚未記錄') : (recorded ? '已記錄' : '不需記錄'),
      ]
    })
    const lines = [headers, ...rows].map(row => row.map(csvEscape).join(','))
    const asOf = summary?.as_of ?? dataStatus?.last_data_as_of ?? fmtDate(new Date().toISOString())
    downloadTextFile(`universe_report_filtered_${asOf}.csv`, `\ufeff${lines.join('\n')}`)
  }

  // ── Early returns ──────────────────────────────────────────────────────────

  if (loading) return <p className="page-loading">載入中…</p>
  if (error)   return <p className="page-error">錯誤：{error}</p>

  if (!items?.length) {
    const isSignalsRunning = signalStatus?.run_status === 'running'
    const isSignalsFailed = signalStatus?.run_status === 'failed'
    const reportParseError = signalStatus?.out_files.universe_report_csv.parse_error

    return (
      <div>
        <h2 className="page-subtitle" style={{ marginBottom: 16 }}>候選股篩選報告</h2>
        {renderTrustNote()}
        {isSignalsRunning ? (
          <div className="alert alert-running" role="status">
            <div className="alert-title">
              <span className="spinner" aria-hidden="true" />
              訊號計算中，候選股報表完成後會自動刷新…
            </div>
            <div className="alert-meta">
              目前後端正在產生 summary.json / universe_report.csv，這不是資料遺失。
            </div>
          </div>
        ) : isSignalsFailed ? (
          <div className="alert alert-error">
            <div className="alert-title">訊號計算失敗</div>
            <div>{signalStatus?.run_error || '請回到訊號 Dashboard 重新產生，或查看後端錯誤。'}</div>
          </div>
        ) : reportParseError ? (
          <div className="alert alert-error">
            <div className="alert-title">候選股報表解析失敗</div>
            <div className="alert-meta">universe_report.csv 無法轉成報表資料，請重新產生訊號。</div>
            <code>{reportParseError}</code>
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleRunSignals}
                disabled={runningSignals}
              >
                {runningSignals ? '啟動中…' : '重新產生訊號'}
              </button>
            </div>
          </div>
        ) : (
          <p className="page-error" style={{ background: '#e3f2fd', color: '#1565c0' }}>
            尚無報表資料，請先至「訊號 Dashboard」執行訊號計算。
          </p>
        )}
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="universe-report-page">
      {/* Header */}
      <div className="page-actions">
        <h2 className="page-subtitle">候選股篩選報告</h2>
        {summary && (
          <span style={{ fontSize: 13, color: '#888' }}>
            as_of: <strong>{summary.as_of}</strong>
            {summary.generated_at && (
              <> · 產生於 {summary.generated_at.slice(0, 16).replace('T', ' ')}</>
            )}
          </span>
        )}
      </div>
      <div className="report-mode-note">
        此報告以收盤日線產生隔日交易計畫；盤中價格可用來監控 5/10/20/60 與缺口是否被破壞，但未收盤 K 不視為正式訊號。
      </div>
      {renderTrustNote()}
      {universeFile && (
        <div
          className={`report-mode-note ${universeFile.parse_error ? 'report-status-error' : ''}`}
          style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}
        >
          <strong>報表狀態</strong>
          <span>as_of: <strong>{universeFile.as_of ?? summary?.as_of ?? '—'}</strong></span>
          {universeFile.row_count != null && <span>筆數: <strong>{universeFile.row_count.toLocaleString()}</strong></span>}
          <span>檔案: {fmtTime(universeFile.last_modified)}</span>
          {signalStatus?.run_status === 'running' && <span>重新計算中</span>}
          {universeFile.parse_error && <span>解析失敗：{universeFile.parse_error}</span>}
        </div>
      )}
      {signalStatus?.run_status === 'running' && (
        <div className="alert alert-running" role="status" style={{ marginBottom: 20 }}>
          <div className="alert-title">
            <span className="spinner" aria-hidden="true" />
            訊號正在重新計算，完成後會自動刷新本頁報表…
          </div>
        </div>
      )}

      {reportSummary && (
        <div className="report-health-board">
          <div className="report-health-card">
            <span>資料完整率</span>
            <strong>{reportSummary.dataOkPct.toFixed(1)}%</strong>
            <em>{reportSummary.dataOkCount}/{reportSummary.total} 檔可判斷 · 全部 {reportSummary.universeTotal}</em>
          </div>
          <button
            type="button"
            className="report-health-card report-health-action"
            onClick={() => showDecisionFilter('enter')}
          >
            <span>可小試</span>
            <strong>{reportSummary.byDecision.enter}</strong>
            <em>{reportSummary.entryRangeCount} 檔有進場區間</em>
          </button>
          <button
            type="button"
            className="report-health-card report-health-action"
            onClick={() => showDecisionFilter('wait_pullback')}
          >
            <span>等回測</span>
            <strong>{reportSummary.byDecision.wait_pullback}</strong>
            <em>等 MA5/MA10 或支撐確認</em>
          </button>
          <button
            type="button"
            className="report-health-card report-health-action report-health-risk"
            onClick={() => showDecisionFilter(reportSummary.byDecision.exit > 0 ? 'exit' : 'reduce')}
          >
            <span>需處理風險</span>
            <strong>{reportSummary.byDecision.exit + reportSummary.byDecision.reduce}</strong>
            <em>{reportSummary.exitPlanCount} 檔有停損/停利價</em>
          </button>
          <button
            type="button"
            className={`report-health-card report-health-action ${reportSummary.dataMissingCount ? 'report-health-warning' : ''}${sigFilter === 'DATA_MISSING' ? ' active' : ''}`}
            onClick={() => setSigFilter(prev => (prev === 'DATA_MISSING' ? 'all' : 'DATA_MISSING'))}
          >
            <span>資料不足</span>
            <strong>{reportSummary.dataMissingCount}</strong>
            <em>持股 {reportSummary.heldCount} 檔</em>
          </button>
          {reportSummary.missingItems.length > 0 && (
            <div className="report-missing-strip">
              {reportSummary.missingItems.map(item => (
                <button
                  type="button"
                  key={item.code}
                  onClick={() => onNavigateAnalysis(item.code)}
                  title="查看資料不足原因"
                >
                  <strong>{item.name}</strong>
                  <em>{item.code}</em>
                  <span>{item.no_buy_reason || '資料不足'}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="journal-progress-board">
        <div className="journal-progress-head">
          <div>
            <h3>候選股復盤進度</h3>
            <span>只統計可小試、等回測、減碼、出場；紀錄來源必須是候選股報表。</span>
          </div>
          <div className="journal-progress-actions">
            <span>{reportAsOf ?? '—'}</span>
            <button
              type="button"
              onClick={handleCopyUnrecordedJournalList}
              disabled={unrecordedJournalRows.length === 0}
            >
              複製待補清單
            </button>
            <button
              type="button"
              onClick={handleBulkCreateUnrecordedJournals}
              disabled={bulkSavingJournals || unrecordedJournalRows.length === 0}
            >
              {bulkSavingJournals ? '批次記錄中' : `批次記錄前 ${Math.min(unrecordedJournalRows.length, 6)} 檔`}
            </button>
          </div>
        </div>
        <div className="journal-progress-grid">
          <button
            type="button"
            className={`journal-progress-card${journalStatusFilter === 'all' ? ' active' : ''}`}
            onClick={() => setJournalStatusFilter('all')}
          >
            <span>可行動清單</span>
            <strong>{journalProgress.actionableCount}</strong>
            <em>目前篩選範圍</em>
          </button>
          <button
            type="button"
            className={`journal-progress-card${journalStatusFilter === 'unrecorded' ? ' active' : ''}${journalProgress.missingActionableCount > 0 ? ' warning' : ''}`}
            onClick={() => setJournalStatusFilter('unrecorded')}
          >
            <span>尚未記錄</span>
            <strong>{journalProgress.missingActionableCount}</strong>
            <em>點選後只看待補復盤</em>
          </button>
          <button
            type="button"
            className={`journal-progress-card${journalStatusFilter === 'recorded' ? ' active' : ''}`}
            onClick={() => setJournalStatusFilter('recorded')}
          >
            <span>已記錄</span>
            <strong>{journalProgress.recordedActionableCount}</strong>
            <em>可行動清單已留理由</em>
          </button>
          <div className="journal-progress-card passive">
            <span>全部報表紀錄</span>
            <strong>{journalProgress.recordedAnyCount}</strong>
            <em>含非可行動股票</em>
          </div>
        </div>
        {unrecordedJournalRows.length > 0 ? (
          <div className="journal-pending-list">
            <div className="journal-pending-head">
              <strong>待補復盤</strong>
              <div>
                <span>先列前 {Math.min(unrecordedJournalRows.length, 6)} 檔；單檔與批次記錄都不會修改持倉或交易紀錄。</span>
                {unrecordedJournalRows.length > 6 && (
                  <button
                    type="button"
                    onClick={() => setJournalStatusFilter('unrecorded')}
                  >
                    顯示全部 {unrecordedJournalRows.length} 檔
                  </button>
                )}
              </div>
            </div>
            <div className="journal-pending-grid">
              {unrecordedJournalRows.slice(0, 6).map(({ item, decision, plan }) => (
                <div className="journal-pending-item" key={item.code}>
                  <div>
                    <button
                      type="button"
                      className="journal-pending-stock"
                      onClick={() => onNavigateAnalysis(item.code)}
                    >
                      {item.name}
                    </button>
                    <em>{item.code} · {decision.label} · {plan.title}</em>
                    <span>關鍵 {decision.keyPrice} / 失效 {decision.invalidation}</span>
                  </div>
                  <button
                    type="button"
                    className="journal-pending-record"
                    onClick={() => handleCreateJournalFromReport(item)}
                    disabled={savingJournalCode === item.code}
                  >
                    {savingJournalCode === item.code ? '記錄中' : '記錄'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className={`journal-pending-empty ${journalProgress.actionableCount > 0 ? 'done' : 'idle'}`}>
            <strong>{journalProgress.actionableCount > 0 ? '可行動清單都已復盤' : '目前沒有可行動復盤股票'}</strong>
            <span>
              {journalProgress.actionableCount > 0
                ? '今天可小試、等回測、減碼、出場的股票都已留下報表決策理由。'
                : '目前篩選範圍內沒有可小試、等回測、減碼或出場的股票。'}
            </span>
          </div>
        )}
      </div>

      <div className="price-position-board">
        <div className="price-position-head">
          <h3>價格位置快篩</h3>
          <span>依目前篩選範圍統計，價格皆使用最新收盤價。</span>
        </div>
        <div className="price-position-grid">
          {(['in_entry_range', 'below_entry_range', 'above_entry_range', 'has_price_plan'] as const).map(position => (
            <button
              type="button"
              key={position}
              className={`price-position-card${pricePositionFilter === position ? ' active' : ''}`}
              onClick={() => setPricePositionFilter(prev => (prev === position ? 'all' : position))}
            >
              <span>{PRICE_POSITION_LABEL[position]}</span>
              <strong>{pricePositionCounts[position]}</strong>
            </button>
          ))}
        </div>
      </div>

      <div className="daily-decision-board">
        <div className="daily-decision-head">
          <div>
            <h3>每日交易決策</h3>
            <span>目前篩選下共 {baseFiltered.length} 檔；先看今日動作，再進詳細線圖確認。</span>
          </div>
          <button
            className={`decision-filter-chip${decisionFilter === 'all' ? ' active' : ''}`}
            onClick={() => setDecisionFilter('all')}
          >
            全部
          </button>
        </div>
        <div className="daily-decision-grid">
          {decisionGroups.map(group => {
            const top = group.rows.slice(0, 4)
            return (
              <button
                key={group.action}
                className={`daily-decision-card${decisionFilter === group.action ? ' active' : ''}`}
                onClick={() => showDecisionFilter(group.action)}
              >
                <span className="decision-card-label">{group.label}</span>
                <strong>{group.rows.length}</strong>
                <span className="decision-card-names">
                  {top.map(({ item }) => `${item.name}${item.code}`).join('、')}
                  {group.rows.length > top.length ? ` +${group.rows.length - top.length}` : ''}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {topPriorityRows.length > 0 && (
        <div className="priority-list-board">
          <div className="priority-list-head">
            <div>
              <h3>今日優先清單</h3>
              <span>
                目前篩選下顯示 {topPriorityRows.length} 檔；照順序先處理風險，再看進攻機會，價格皆為收盤計畫價。
              </span>
            </div>
            <button
              className="decision-filter-chip"
              onClick={resetReportFilters}
            >
              清除篩選
            </button>
          </div>
          <div className="priority-list-grid">
            {topPriorityRows.map(({ item, decision, plan }, index) => {
              const entryDistance = getEntryDistance(item)
              const stopDistance = getStopDistance(item)
              const targetDistance = getTargetDistance(item)
              const alreadyRecorded = journalRecordedCodes.has(item.code)
              const journalStatusLabel = alreadyRecorded ? '已復盤' : '待復盤'
              const journalStatusClass = alreadyRecorded ? 'journal-status-done' : 'journal-status-pending'
              return (
                  <div className={`priority-item priority-${decision.action}`} key={item.code}>
                    <div className="priority-item-main">
                      <span className="priority-rank">{index + 1}</span>
                      <div>
                        <button
                          type="button"
                          className="report-stock-link"
                          onClick={() => onNavigateAnalysis(item.code)}
                        >
                          {item.name}
                        </button>
                        <em>{item.code} · {resolveMarket(item)} · {decision.identity}</em>
                      </div>
                      <span className={`decision-badge ${decision.cls}`}>{decision.label}</span>
                    </div>

                    <div className="priority-price-grid">
                      <div>
                        <span>觀察價</span>
                        <strong>{decision.keyPrice}</strong>
                      </div>
                      <div>
                        <span>停損/失效</span>
                        <strong>{decision.invalidation}</strong>
                        {stopDistance && <em className={`price-distance ${stopDistance.cls}`}>{stopDistance.label}</em>}
                      </div>
                      <div>
                        <span>進場區間</span>
                        <strong>
                          {item.entry_price_low != null && item.entry_price_high != null
                            ? `${fmtPrice(item.entry_price_low)}–${fmtPrice(item.entry_price_high)}`
                            : '—'}
                        </strong>
                        {entryDistance && <em className={`price-distance ${entryDistance.cls}`}>{entryDistance.label}</em>}
                      </div>
                      <div>
                        <span>停利目標</span>
                        <strong>{item.target_price != null ? fmtPrice(item.target_price) : '—'}</strong>
                        {targetDistance && <em className={`price-distance ${targetDistance.cls}`}>{targetDistance.label}</em>}
                      </div>
                    </div>

                    <p className="priority-reason">{decision.oneLine}</p>
                    <div className="priority-footer">
                      <span className={plan.cls}>{plan.title}</span>
                      <em>{plan.advice}</em>
                      {item.score != null && <strong>分數 {item.score}</strong>}
                      <span className={`journal-status-badge ${journalStatusClass}`}>{journalStatusLabel}</span>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleCreateJournalFromReport(item)}
                        disabled={alreadyRecorded || savingJournalCode === item.code}
                      >
                        {alreadyRecorded ? '已記錄' : savingJournalCode === item.code ? '記錄中' : '記錄'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => onNavigateAnalysis(item.code)}
                      >
                        詳細
                      </button>
                    </div>
                  </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── 總覽卡片 ─────────────────────────────────────────────────────── */}
      <div className="portfolio-summary" style={{ marginBottom: 20, flexWrap: 'wrap' }}>
        <button
          type="button"
          className={`summary-item report-summary-action${activeFilterLabels.length === 0 ? ' active' : ''}`}
          onClick={resetReportFilters}
        >
          <span className="summary-label">目前範圍</span>
          <span className="summary-value">{stats?.total ?? 0}</span>
          <span className="summary-label">全部 {stats?.universeTotal ?? items.length}</span>
        </button>
        <button
          type="button"
          className={`summary-item report-summary-action${mktFilter === 'TWSE' ? ' active' : ''}`}
          onClick={() => setMktFilter(prev => (prev === 'TWSE' ? 'all' : 'TWSE'))}
        >
          <span className="summary-label">TWSE 上市</span>
          <span className="summary-value">{stats?.byMarket.TWSE ?? 0}</span>
        </button>
        <button
          type="button"
          className={`summary-item report-summary-action${mktFilter === 'TPEX' ? ' active' : ''}`}
          onClick={() => setMktFilter(prev => (prev === 'TPEX' ? 'all' : 'TPEX'))}
        >
          <span className="summary-label">TPEX 上櫃</span>
          <span className="summary-value">{stats?.byMarket.TPEX ?? 0}</span>
        </button>
        <button
          type="button"
          className={`summary-item report-summary-action${mktFilter === 'ETF' ? ' active' : ''}`}
          onClick={() => setMktFilter(prev => (prev === 'ETF' ? 'all' : 'ETF'))}
        >
          <span className="summary-label">ETF</span>
          <span className="summary-value">{stats?.byMarket.ETF ?? 0}</span>
        </button>

        {/* 各訊號計數 */}
        {Object.entries(stats?.bySignal ?? {})
          .sort((a, b) => {
            const order = ['entry_confirmed','ready_to_enter','watchlist','hold','take_profit_warning','exit_warning','invalidated','DATA_MISSING']
            return order.indexOf(a[0]) - order.indexOf(b[0])
          })
          .map(([sig, cnt]) => {
            const signal = sig as SignalFilter
            return (
              <button
                type="button"
                key={sig}
                className={`summary-item report-summary-action${sigFilter === signal ? ' active' : ''}`}
                style={{ minWidth: 90 }}
                onClick={() => setSigFilter(prev => (prev === signal ? 'all' : signal))}
              >
                <span className="summary-label">{SIG_LABEL[sig] ?? sig}</span>
                <span className="summary-value" style={{ fontSize: 18 }}>{cnt}</span>
              </button>
            )
          })}
      </div>

      {/* ── 篩選列 ───────────────────────────────────────────────────────── */}
      <div className="report-filters">
        <div className="report-filter-group">
          <label className="report-filter-label">訊號狀態</label>
          <select
            className="report-filter-select"
            value={sigFilter}
            onChange={e => setSigFilter(e.target.value as SignalFilter)}
          >
            <option value="all">全部</option>
            {ALL_SIG_FILTERS.slice(1).map(s => (
              <option key={s} value={s}>{SIG_LABEL[s]}</option>
            ))}
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">市場</label>
          <select
            className="report-filter-select"
            value={mktFilter}
            onChange={e => setMktFilter(e.target.value as MarketFilter)}
          >
            <option value="all">全部</option>
            <option value="TWSE">TWSE 上市</option>
            <option value="TPEX">TPEX 上櫃</option>
            <option value="ETF">ETF</option>
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">推薦方案</label>
          <select
            className="report-filter-select"
            value={planFilter}
            onChange={e => setPlanFilter(e.target.value as PlanFilter)}
          >
            <option value="all">全部</option>
            <option value="confluence">雙重共振</option>
            <option value="steady_momentum">穩健動能</option>
            <option value="old_wang">老王短波段</option>
            <option value="no_entry">暫不進場</option>
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">持股狀態</label>
          <select
            className="report-filter-select"
            value={holdingFilter}
            onChange={e => setHoldingFilter(e.target.value as HoldingFilter)}
          >
            <option value="all">全部</option>
            <option value="holding">目前持股</option>
            <option value="not_holding">非持股</option>
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">今日動作</label>
          <select
            className="report-filter-select"
            value={decisionFilter}
            onChange={e => setDecisionFilter(e.target.value as DecisionAction)}
          >
            <option value="all">全部</option>
            {DECISION_ORDER.map(action => (
              <option key={action} value={action}>{DECISION_LABEL[action]}</option>
            ))}
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">價格位置</label>
          <select
            className="report-filter-select"
            value={pricePositionFilter}
            onChange={e => setPricePositionFilter(e.target.value as PricePositionFilter)}
          >
            <option value="all">全部位置</option>
            <option value="in_entry_range">進場區間內</option>
            <option value="below_entry_range">低於進場區</option>
            <option value="above_entry_range">高於進場區</option>
            <option value="has_price_plan">有完整價格計畫</option>
          </select>
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">復盤狀態</label>
          <select
            className="report-filter-select"
            value={journalStatusFilter}
            onChange={e => setJournalStatusFilter(e.target.value as JournalStatusFilter)}
          >
            <option value="all">全部復盤</option>
            <option value="unrecorded">尚未記錄</option>
            <option value="recorded">已記錄</option>
          </select>
        </div>

        <div className="report-filter-group" style={{ flex: 1 }}>
          <label className="report-filter-label">關鍵字</label>
          <input
            className="report-filter-input"
            type="text"
            placeholder="代號或名稱"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
          />
        </div>

        <div className="report-filter-group">
          <label className="report-filter-label">排序</label>
          <select
            className="report-filter-select"
            value={sortMode}
            onChange={e => setSortMode(e.target.value as ReportSortMode)}
          >
            <option value="daily_priority">今日優先</option>
            <option value="score_desc">分數最高</option>
            <option value="reward_risk_desc">R/R 最好</option>
            <option value="entry_near">離進場最近</option>
            <option value="target_near">離目標最近</option>
          </select>
        </div>

        <div style={{ alignSelf: 'flex-end', fontSize: 13, color: '#888', paddingBottom: 6 }}>
          顯示 {filtered.length} / {items.length} 筆 · {REPORT_SORT_LABEL[sortMode]}
        </div>

        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ alignSelf: 'flex-end' }}
          onClick={handleDownloadFilteredCsv}
          disabled={filtered.length === 0}
        >
          下載目前結果 CSV
        </button>
      </div>

      <div className="report-snapshot-bar">
        <div>
          <span>{reportSnapshot}</span>
          {journalMessage && (
            <em className="report-snapshot-message">{journalMessage}</em>
          )}
          {snapshotTopRows.length > 0 && (
            <div className="report-snapshot-top">
              {snapshotTopRows.map(({ item, decision, plan, entryDistance, stopDistance, targetDistance }, index) => {
                const alreadyRecorded = journalRecordedCodes.has(item.code)
                return (
                  <div
                    key={item.code}
                  >
                    <button
                      type="button"
                      className="report-snapshot-stock"
                      onClick={() => onNavigateAnalysis(item.code)}
                    >
                      {index + 1}. {item.name}
                    </button>
                    <em>{item.code} · {decision.label} · {plan.title}</em>
                    <span>
                      收盤 {fmtPrice(item.close)}
                      {entryDistance ? ` / ${entryDistance.label}` : ''}
                      {stopDistance ? ` / ${stopDistance.label}` : ''}
                      {targetDistance ? ` / ${targetDistance.label}` : ''}
                    </span>
                    <button
                      type="button"
                      className="report-snapshot-journal"
                      onClick={() => handleCreateJournalFromReport(item)}
                      disabled={alreadyRecorded || savingJournalCode === item.code}
                      title={alreadyRecorded ? '此資料日已建立決策日誌' : '把目前報表判斷存成決策日誌，不修改交易紀錄'}
                    >
                      {alreadyRecorded ? '已記錄' : savingJournalCode === item.code ? '記錄中...' : '記錄決策'}
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <button
          type="button"
          className="report-copy-snapshot"
          onClick={handleCopySnapshot}
        >
          {copiedSnapshot ? '已複製' : '複製摘要'}
        </button>
      </div>

      {activeFilterLabels.length > 0 && (
        <div className="report-active-filters">
          <span>目前篩選</span>
          {activeFilterLabels.map(filter => (
            <button
              type="button"
              className="report-filter-chip"
              key={filter.key}
              onClick={filter.clear}
              title={`清除${filter.label}`}
            >
              {filter.label}
              <span aria-hidden="true">×</span>
            </button>
          ))}
          <button type="button" className="report-clear-filters" onClick={resetReportFilters}>清除全部</button>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="report-empty-state">
          <strong>
            {journalStatusFilter === 'unrecorded'
              ? (journalProgress.actionableCount > 0 ? '復盤已完成' : '目前沒有可行動復盤股票')
              : '沒有符合條件的股票'}
          </strong>
          <span>
            {journalStatusFilter === 'unrecorded'
              ? journalProgress.actionableCount > 0
                ? '目前篩選範圍內可小試、等回測、減碼、出場的股票都已留下報表決策理由。'
                : '目前篩選範圍內沒有可小試、等回測、減碼或出場的股票。'
              : `目前共有 ${items.length} 檔追蹤股票，但篩選條件把結果縮到 0 筆。${activeFilterLabels.length > 0 ? ' 可以先清除篩選，再重新看今日優先清單。' : ' 請確認報表資料是否已更新。'}`
            }
          </span>
          <div className="report-empty-actions">
            {journalStatusFilter === 'unrecorded' && journalProgress.recordedActionableCount > 0 && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setJournalStatusFilter('recorded')}>
                查看已復盤
              </button>
            )}
            {activeFilterLabels.length > 0 && (
              <button type="button" className="btn btn-primary btn-sm" onClick={resetReportFilters}>
                清除篩選
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── 表格 ─────────────────────────────────────────────────────────── */}
      {filtered.length > 0 && (
      <div className="table-wrap report-table-wrap">
        <table className="data-table report-table">
          <thead>
            <tr>
              <th>代號 / 名稱</th>
              <th>市場</th>
              <th>今日動作</th>
              <th>推薦方案 / 建議</th>
              <th>進場區間</th>
              <th>出場 / 停損</th>
              <th>停利目標</th>
              <th>訊號 / 分數</th>
              <th>收盤</th>
              <th>趨勢 / RSI</th>
              <th>型態</th>
              <th>詳細</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(item => {
              const market   = resolveMarket(item)
              const expanded = expandedCode === item.code
              const reasons  = item.reasons?.split(' | ').filter(Boolean) ?? []
              const dailyDecision = getDailyDecision(item)
              const plan = getRecommendedPlan(item)
              const hasChecklist = (item.daily_checklist?.length ?? 0) > 0
              const entryDistance = getEntryDistance(item)
              const stopDistance = getStopDistance(item)
              const targetDistance = getTargetDistance(item)
              const alreadyRecorded = journalRecordedCodes.has(item.code)
              const actionableJournal = ACTIONABLE_REPORT_JOURNAL_ACTIONS.has(dailyDecision.action)
              const journalStatusLabel = actionableJournal
                ? (alreadyRecorded ? '已復盤' : '待復盤')
                : (alreadyRecorded ? '已復盤' : '不需復盤')
              const journalStatusClass = actionableJournal
                ? (alreadyRecorded ? 'journal-status-done' : 'journal-status-pending')
                : (alreadyRecorded ? 'journal-status-done' : 'journal-status-muted')

              return (
                <Fragment key={item.code}>
                  <tr>
                    {/* 代號 / 名稱 */}
                    <td>
                      <button
                        className="report-stock-link"
                        onClick={() => onNavigateAnalysis(item.code)}
                        title="查看詳細技術分析"
                      >
                        {item.name}
                      </button>
                      <br />
                      <span className="td-id">{item.code}</span>
                    </td>

                    {/* 市場 */}
                    <td>
                      <span style={{ fontSize: 12, color: '#666' }}>{market}</span>
                    </td>

                    <td className="daily-action-cell">
                      <div className="daily-action-badges">
                        <span className={`decision-badge ${dailyDecision.cls}`}>{dailyDecision.label}</span>
                        <span className={`journal-status-badge ${journalStatusClass}`}>{journalStatusLabel}</span>
                      </div>
                      <strong title={dailyDecision.oneLine}>{dailyDecision.oneLine}</strong>
                    </td>

                    {/* 推薦方案 / 建議 */}
                    <td className="report-plan-cell">
                      <span className={plan.cls}>{plan.title}</span>
                      <strong>{plan.advice}</strong>
                      <div className="report-plan-tags">
                        {hasOldWangTag(item) && item.old_wang_score != null && (
                          <em>老王 {item.old_wang_score}{item.old_wang_raw_score != null ? ` / 原始 ${item.old_wang_raw_score}` : ''}</em>
                        )}
                        {item.steady_momentum_flag && item.steady_momentum_score != null && (
                          <em>穩健動能 {item.steady_momentum_score}</em>
                        )}
                        {item.fundamental_data_ok && item.fundamental_quality_score != null && (
                          <em>基本面避雷 品質 {item.fundamental_quality_score}</em>
                        )}
                        {item.holding_shares != null && item.holding_shares > 0 && (
                          <em>
                            持有 {item.holding_shares.toLocaleString()} 股
                            {item.holding_position_pct != null ? ` / 投組 ${item.holding_position_pct.toFixed(2)}%` : ''}
                          </em>
                        )}
                        {item.position_size_pct != null && item.position_size_pct > 0 && (
                          <em>新進場 {item.position_size_pct}%</em>
                        )}
                      </div>
                    </td>

                    {/* 進場區間 */}
                    <td className="report-price-cell">
                      {item.entry_price_low != null && item.entry_price_high != null ? (
                        <>
                          <strong>{fmtPrice(item.entry_price_low)}–{fmtPrice(item.entry_price_high)}</strong>
                          {entryDistance && (
                            <em className={`price-distance ${entryDistance.cls}`}>{entryDistance.label}</em>
                          )}
                        </>
                      ) : (
                        <span className="muted-dash">—</span>
                      )}
                    </td>

                    {/* 出場 / 停損 */}
                    <td className="report-price-cell">
                      {item.stop_price != null ? (
                        <>
                          <strong>{fmtPrice(item.stop_price)}</strong>
                          {item.risk_pct != null && <span>風險 {item.risk_pct.toFixed(1)}%</span>}
                          <span title={dailyDecision.invalidation}>失效 {dailyDecision.invalidation}</span>
                          {stopDistance && (
                            <em className={`price-distance ${stopDistance.cls}`}>{stopDistance.label}</em>
                          )}
                        </>
                      ) : <span className="muted-dash">—</span>}
                    </td>

                    {/* 停利目標 */}
                    <td className="report-price-cell">
                      {item.target_price != null ? (
                        <>
                          <strong>{fmtPrice(item.target_price)}</strong>
                          {item.reward_risk_ratio != null && <span>R/R {item.reward_risk_ratio.toFixed(2)}</span>}
                          {targetDistance && (
                            <em className={`price-distance ${targetDistance.cls}`}>{targetDistance.label}</em>
                          )}
                        </>
                      ) : <span className="muted-dash">—</span>}
                    </td>

                    {/* 訊號 / 分數 */}
                    <td>
                      <span className={SIG_CLASS[item.internal_signal] ?? 'signal-badge sig-na'} style={{ fontSize: 12 }}>
                        {SIG_LABEL[item.internal_signal] ?? item.internal_signal}
                      </span>
                      {item.entry_type && (
                        <span style={{ display: 'block', fontSize: 11, color: '#888', marginTop: 2 }}>
                          {item.entry_type === 'breakout' ? '突破' : '回測'}
                        </span>
                      )}
                      <br />
                      {item.score != null ? (
                        <span className={`score-badge ${item.score >= 85 ? 'score-high' : item.score >= 65 ? 'score-mid' : 'score-low'}`}>
                          {item.score}
                        </span>
                      ) : <span style={{ color: '#bbb' }}>—</span>}
                    </td>

                    {/* 收盤 */}
                    <td style={{ fontWeight: 600 }}>
                      {fmtPrice(item.close)}
                    </td>

                    {/* 趨勢 / RSI */}
                    <td className="report-trend-cell">
                      {TREND_ICON(item.long_trend, true)}
                      {' / '}
                      {TREND_ICON(item.short_trend, true)}
                      <br />
                      {item.rsi14 != null ? (
                        <span style={{
                          fontWeight: 600,
                          color: item.rsi14 > 75 ? '#c62828' : item.rsi14 < 30 ? '#2e7d32' : '#555',
                        }}>
                          {item.rsi14.toFixed(1)}
                        </span>
                      ) : <span style={{ color: '#bbb' }}>—</span>}
                    </td>

                    {/* 型態 */}
                    <td style={{ fontSize: 12 }}>
                      {item.pattern_type && item.pattern_type !== 'none' ? (
                        <>
                          <span>{PATTERN_LABEL[item.pattern_type] ?? item.pattern_type}</span>
                          <span style={{ color: '#888', marginLeft: 4 }}>
                            {PATTERN_STATUS_LABEL[item.pattern_status] ?? item.pattern_status}
                          </span>
                        </>
                      ) : <span style={{ color: '#bbb' }}>—</span>}
                    </td>

                    {/* 詳細 */}
                    <td className="report-row-actions">
                      <button
                        className="btn btn-primary"
                        style={{ fontSize: 12, padding: '5px 12px' }}
                        onClick={() => onNavigateAnalysis(item.code)}
                      >
                        詳細
                      </button>
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => handleCreateJournalFromReport(item)}
                        disabled={alreadyRecorded || savingJournalCode === item.code}
                        title={alreadyRecorded ? '此資料日已建立決策日誌' : '把目前報表判斷存成決策日誌，不修改交易紀錄'}
                      >
                        {alreadyRecorded ? '已記錄' : savingJournalCode === item.code ? '記錄中' : '記錄'}
                      </button>
                      {(reasons.length > 0 || hasChecklist || item.no_buy_reason) && (
                        <button
                          className="btn btn-ghost btn-xs"
                          onClick={() => setExpandedCode(expanded ? null : item.code)}
                        >
                          {expanded ? '收起' : '理由'}
                        </button>
                      )}
                    </td>
                  </tr>

                  {/* 展開：作戰檢查與 reasons 清單 */}
                  {expanded && (reasons.length > 0 || (item.daily_checklist?.length ?? 0) > 0 || item.no_buy_reason) && (
                    <tr>
                      <td colSpan={12} style={{ background: '#f5f7fa', padding: '8px 18px' }}>
                        {item.no_buy_reason && <p className="report-expanded-reason">{item.no_buy_reason}</p>}
                        <DailyChecklist items={item.daily_checklist} compact />
                        {reasons.length > 0 && (
                          <ul className="panel-list" style={{ margin: 0 }}>
                            {reasons.map((r, i) => <li key={i}>{r}</li>)}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  )
}
