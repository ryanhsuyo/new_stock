import { type KeyboardEvent, type RefObject, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import DailyChecklist from '../components/DailyChecklist'
import NoSignalExplainer from '../components/NoSignalExplainer'
import type { DailyBrief, DailyBriefStock, DailyBriefTask, DailyCheckReport, DataStatus, DecisionJournalCreate, DecisionJournalDecision, DecisionJournalEntry, DecisionJournalSummary, FileInfo, FundamentalsPriorityMergeResult, FundamentalsStatus, ManualWatchlistReview, ManualWatchlistReviewItem, MarketNoteInput, PmWorklist, SignalsSummary, SignalsStatus, StockRecommendation, StockUniverseItem, UniverseReportReviewWorkflow, UpdateWorkflowStatus, WorkflowPortfolioTask, WorkflowStatus } from '../types'

type RecommendationStrategy = 'core' | 'old_wang' | 'buffett'

interface WorkflowUniversePendingItem {
  code: string
  name: string
  action: string
  label: string
  reason: string
  key_price?: string | null
  invalidation?: string | null
  priority?: number
}

function isWorkflowUniversePendingItem(value: unknown): value is WorkflowUniversePendingItem {
  return Boolean(
    value &&
    typeof value === 'object' &&
    'code' in value &&
    'name' in value &&
    typeof (value as { code?: unknown }).code === 'string' &&
    typeof (value as { name?: unknown }).name === 'string'
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function StatusDot({ exists }: { exists: boolean }) {
  return (
    <span style={{ color: exists ? '#2e7d32' : '#bbb', fontSize: 16, marginRight: 6 }}>
      {exists ? '●' : '○'}
    </span>
  )
}

function StatusRow({
  label,
  info,
  optional,
  extra,
}: {
  label: string
  info: FileInfo
  optional?: boolean
  extra?: string
}) {
  const fmtTime = (s?: string) => s ? s.slice(0, 16).replace('T', ' ') : ''

  return (
    <tr>
      <td style={{ width: 24, verticalAlign: 'middle' }}>
        <StatusDot exists={info.exists} />
      </td>
      <td style={{ fontWeight: 600, paddingRight: 20, whiteSpace: 'nowrap' }}>
        {label}
      </td>
      <td style={{ fontSize: 13, color: '#555' }}>
        {info.exists ? (
          <>
            {info.as_of && <span style={{ marginRight: 16 }}>as_of: <strong>{info.as_of}</strong></span>}
            {info.generated_at && <span style={{ marginRight: 16, color: '#666' }}>產生: {fmtTime(info.generated_at)}</span>}
            {info.row_count != null && <span style={{ marginRight: 16, color: '#666' }}>筆數: {info.row_count.toLocaleString()}</span>}
            {info.last_modified && <span style={{ color: '#888' }}>檔案: {fmtTime(info.last_modified)}</span>}
            {info.status_label && (
              <span style={{ marginLeft: 16, color: info.update_required ? '#b45309' : '#2e7d32', fontWeight: 700 }}>
                {info.status_label}
              </span>
            )}
            {info.parse_error && (
              <span
                style={{ marginLeft: 16, color: '#b71c1c', fontWeight: 700 }}
                title={info.parse_error}
              >
                解析失敗
              </span>
            )}
            {extra && <span style={{ marginLeft: 16, color: '#92400e', fontWeight: 700 }}>{extra}</span>}
          </>
        ) : (
          <span style={{ color: '#aaa' }}>{optional ? '不存在（選填）' : '不存在'}</span>
        )}
      </td>
    </tr>
  )
}

function ParseErrorAlert({ status }: { status: SignalsStatus | null }) {
  const files = status ? [
    { label: 'summary.json', info: status.out_files.summary_json },
    { label: 'universe_report.csv', info: status.out_files.universe_report_csv },
    { label: 'daily_brief.json', info: status.out_files.daily_brief_json },
  ].filter(item => item.info.parse_error) : []

  if (!files.length) return null

  return (
    <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
      <div className="alert-title">輸出檔案解析失敗</div>
      <div className="alert-meta">請重新產生訊號；若仍失敗，檢查後端寫檔流程或手動修改的 JSON / CSV 格式。</div>
      <div className="parse-error-list">
        {files.map(file => (
          <div key={file.label}>
            <strong>{file.label}</strong>
            <code>{file.info.parse_error}</code>
          </div>
        ))}
      </div>
    </div>
  )
}

function fmtChipLots(value: number | null): string {
  if (value === null || value === undefined) return '待匯入'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toLocaleString()}張`
}

function fmtChipPct(value: number | null): string {
  if (value === null || value === undefined) return '待匯入'
  return `${value.toFixed(2)}%`
}

function fmtVolume(value: number | null): string {
  if (value === null || value === undefined) return '—'
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}億`
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}萬`
  return value.toLocaleString()
}

const STRATEGY_OPTIONS: Array<{ key: RecommendationStrategy; label: string; desc: string }> = [
  { key: 'core', label: '核心', desc: '只看正式買點' },
  { key: 'old_wang', label: '老王', desc: '只看老王短波段旗標' },
  { key: 'buffett', label: '巴菲特', desc: '只看長期品質價值條件' },
]

const DECISION_OPTIONS: Array<{ key: DecisionJournalDecision; label: string }> = [
  { key: 'hold', label: '續抱' },
  { key: 'watch', label: '觀察' },
  { key: 'skip', label: '不進場' },
  { key: 'buy', label: '買進' },
  { key: 'reduce', label: '減碼' },
  { key: 'sell', label: '賣出' },
]

const DECISION_LABELS = Object.fromEntries(DECISION_OPTIONS.map(item => [item.key, item.label])) as Record<string, string>

const DATA_REPAIR_COMMAND = [
  'cd /Users/ryan/Desktop/code/new_stock/backend',
  'python3 scripts/daily_update.py --months 12',
].join('\n')

function todayInputValue(): string {
  const today = new Date()
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset())
  return today.toISOString().slice(0, 10)
}

type DecisionJournalDraft = Partial<DecisionJournalCreate> & { nonce: number }

function workflowOutcomeMessage(workflow: WorkflowStatus): string {
  const review = workflow.readiness_review
  if (!review) {
    return workflow.can_trade_today ? '工作流已刷新，可進行決策' : workflow.headline
  }
  if (review.top_blocker_key) {
    const blocker = review.sections.find(section => section.key === review.top_blocker_key)
    return blocker
      ? `仍需處理：${blocker.label} - ${blocker.message}`
      : review.overall_label
  }
  const warning = review.sections.find(section => section.status === 'warning')
  if (warning) {
    return `閉環可用但有待補：${warning.label} - ${warning.message}`
  }
  return '每日資料閉環已就緒'
}

function workflowActionToDecision(action?: string | null): DecisionJournalDecision {
  if (action === 'exit') return 'sell'
  if (action === 'reduce') return 'reduce'
  if (action === 'enter') return 'buy'
  if (action === 'avoid') return 'skip'
  if (action === 'hold') return 'hold'
  return 'watch'
}

const STRATEGY_GUIDE = [
  {
    key: 'core',
    title: '核心技術',
    role: '正式進出場',
    detail: '用支撐壓力、MA20/MA60、型態、量能與 R/R 決定是否可分批進場。',
  },
  {
    key: 'old_wang',
    title: '老王短波段',
    role: '大盤風控與強勢股',
    detail: '看 TSE/OTC、MA5/MA10、族群輪動、爆大量低點與前高壓力，避免追高。',
  },
  {
    key: 'buffett',
    title: '巴菲特長期價值',
    role: '基本面觀察',
    detail: '看 ROE、自由現金流、負債安全、成長與估值；需 fundamentals.json，不參與短線買賣。',
  },
]

const BUFFETT_SCORE_LABELS = [
  { key: 'buffett_quality_score', label: '品質' },
  { key: 'buffett_safety_score', label: '安全' },
  { key: 'buffett_value_score', label: '估值' },
  { key: 'buffett_growth_score', label: '成長' },
] as const

const SIGNAL_TEXT: Record<string, string> = {
  entry_confirmed: '入場確認',
  ready_to_enter: '準備入場',
  watchlist: '觀察中',
  hold: '持股中',
  take_profit_warning: '停利觀察',
  exit_warning: '出場警示',
  invalidated: '訊號失效',
  DATA_MISSING: '資料不足',
}

function buffettScoreClass(value?: number | null): string {
  if (value == null) return 'missing'
  if (value >= 70) return 'good'
  if (value >= 45) return 'mid'
  return 'weak'
}

const OLD_WANG_MARKET_TEXT: Record<string, string> = {
  strong: '偏多',
  caution: '觀察',
  risk: '風險',
  unknown: '未知',
}

const todayTaipei = () => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Taipei',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')}`
}

const splitLines = (value: string) =>
  value.split('\n').map(line => line.trim()).filter(Boolean)

const emptyMarketNoteForm = (): MarketNoteInput => ({
  date: todayTaipei(),
  title: '',
  risk_level: 'caution',
  headline: '',
  position_guidance: '',
  market_actions: [],
})

function OldWangMarketBox({ summary }: { summary: SignalsSummary | null }) {
  const ctx = summary?.market_context
  if (!ctx) return null
  const regime = ctx.old_wang_market_regime || 'unknown'
  const cls = regime === 'strong' ? 'strong' : regime === 'risk' ? 'risk' : 'caution'

  return (
    <div className={`old-wang-market-box ${cls}`}>
      <div>
        <span className="old-wang-market-label">老王大盤濾網</span>
        <strong>{OLD_WANG_MARKET_TEXT[regime] ?? regime}</strong>
      </div>
      <p>{ctx.old_wang_market_reason || ctx.reason || '尚無大盤濾網說明'}</p>
      <em>來源 {ctx.old_wang_market_source || ctx.benchmark_code || '—'} · {ctx.old_wang_market_filter || 'neutral'}</em>
    </div>
  )
}

function ManualMarketNoteBox({ summary }: { summary: SignalsSummary | null }) {
  const note = summary?.manual_market_note
  if (!note) return null
  const cls = note.risk_level === 'risk' ? 'risk' : note.risk_level === 'caution' ? 'caution' : 'strong'
  const actions = note.market_actions?.slice(0, 4) ?? []
  const staleDays = note.stale_trading_days ?? 0
  const statusText = note.is_stale
    ? `舊筆記 · 距基準日 ${staleDays} 個交易日`
    : note.status_label ?? '最新筆記'

  return (
    <div className={`manual-market-note ${cls} ${note.is_stale ? 'stale' : ''}`}>
      <div className="manual-market-note-main">
        <div>
          <span className="old-wang-market-label">
            人工盤後筆記 · {note.date}
            {note.applies_to_as_of && ` / 訊號基準 ${note.applies_to_as_of}`}
          </span>
          <span className={`manual-note-status ${note.is_stale ? 'stale' : 'fresh'}`}>
            {statusText}
          </span>
          <strong>{note.title}</strong>
        </div>
        <p>{note.headline}</p>
        {note.is_stale && note.stale_reason && <p className="manual-note-warning">{note.stale_reason}</p>}
        {note.position_guidance && <em>{note.position_guidance}</em>}
      </div>
      {actions.length > 0 && (
        <ul>
          {actions.map((action, index) => <li key={index}>{action}</li>)}
        </ul>
      )}
    </div>
  )
}

function StrategyGuideBox({
  status,
  fundamentalsStatus,
  mergeResult,
  merging,
  signalsBusy,
  onPreviewMerge,
  onApplyMerge,
  onRunSignals,
}: {
  status: SignalsStatus | null
  fundamentalsStatus: FundamentalsStatus | null
  mergeResult: FundamentalsPriorityMergeResult | null
  merging: boolean
  signalsBusy: boolean
  onPreviewMerge: () => Promise<void>
  onApplyMerge: () => Promise<void>
  onRunSignals: () => void
}) {
  const [copiedFillTargets, setCopiedFillTargets] = useState(false)
  const fundamentals = status?.data_files.fundamentals_json
  const complete = fundamentalsStatus?.complete_count ?? 0
  const total = fundamentalsStatus?.total_codes ?? 0
  const incomplete = fundamentalsStatus?.incomplete_count ?? 0
  const missing = fundamentalsStatus?.missing_count ?? 0
  const nextFillTargets = fundamentalsStatus?.next_fill_targets?.slice(0, 10) ?? []
  const missingFields = Object.entries(fundamentalsStatus?.field_missing_counts ?? {}).slice(0, 5)
  const labels = fundamentalsStatus?.field_labels ?? {}
  const fillReadiness = fundamentalsStatus?.priority_fill_readiness
  const fillGuide = fundamentalsStatus?.priority_fill_guide
  const workflowSummary = fundamentalsStatus?.workflow_summary
  const exampleValues = fillGuide?.example_values ?? {}
  const priorityValidation = fundamentalsStatus?.priority_csv_validation
  const priorityValidationIssues = [
    ...(priorityValidation?.errors ?? []).map(issue => ({ ...issue, kind: '錯誤' })),
    ...(priorityValidation?.warnings ?? []).map(issue => ({ ...issue, kind: '警告' })),
  ].slice(0, 4)
  const mergePartialRows = mergeResult?.row_statuses?.filter(row => row.status === 'partial').slice(0, 4) ?? []
  const ready = Boolean(fundamentals?.exists && complete > 0)
  const pct = fundamentalsStatus?.coverage_pct ?? 0
  const canPreviewPriorityFill = fillReadiness?.can_preview ?? true
  const canMergePriorityFill = fillReadiness?.can_merge ?? true
  const readinessClass = fillReadiness?.status === 'ready_to_merge'
    ? 'ready'
    : fillReadiness?.status === 'ready_to_preview'
      ? 'preview'
    : fillReadiness?.status === 'invalid'
      ? 'danger'
      : 'muted'
  const copyFillTargets = async () => {
    const rows = nextFillTargets.map((target, index) => {
      const missingLines = target.missing_fields.map(field => {
        const label = labels[field] ?? field
        const example = exampleValues[field] ? `，範例 ${exampleValues[field]}` : ''
        return `    - ${label} (${field}${example})`
      })
      return [
        `${index + 1}. ${target.name} ${target.code} - ${target.priority_reason}，缺 ${target.missing_count} 欄`,
        ...missingLines,
      ].join('\n')
    })
    const text = [
      '巴菲特基本面優先補資料清單',
      `覆蓋率 ${complete}/${total}，優先補 ${nextFillTargets.length} 檔`,
      fillGuide?.format_note ?? '',
      '',
      rows.join('\n\n'),
    ].filter(Boolean).join('\n')

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedFillTargets(true)
      window.setTimeout(() => setCopiedFillTargets(false), 1600)
    } catch (error) {
      console.error('copy fundamentals fill targets failed', error)
    }
  }

  return (
    <div className="strategy-guide">
      {STRATEGY_GUIDE.map(item => (
        <div className="strategy-guide-item" key={item.key}>
          <span>{item.role}</span>
          <strong>{item.title}</strong>
          <p>{item.detail}</p>
        </div>
      ))}
      <div className={`strategy-guide-status ${ready ? 'ready' : 'missing'}`}>
        <span>巴菲特資料</span>
        <strong>{total > 0 ? `${complete}/${total} 完整` : fundamentals?.exists ? '已匯入' : '尚未匯入'}</strong>
        <div className="fundamentals-progress" aria-label="巴菲特基本面資料覆蓋率">
          <i style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
        </div>
        <p>
          {ready
            ? `可評分 ${complete} 檔，覆蓋率 ${pct.toFixed(1)}%。`
            : fundamentals?.exists
              ? `尚無完整可評分股票；缺欄位 ${incomplete} 檔，缺整檔資料 ${missing} 檔。`
              : '建立 backend/data/fundamentals.json 後，巴菲特方案才會產生候選。'}
        </p>
      </div>
      {workflowSummary && (
        <div className={`fundamentals-workflow-card stage-${workflowSummary.stage}`}>
          <div className="fundamentals-workflow-head">
            <div>
              <span>Buffett PM 工作流</span>
              <strong>{workflowSummary.headline}</strong>
              <p>{workflowSummary.detail}</p>
            </div>
            <div className="fundamentals-workflow-action">
              <em>{workflowSummary.coverage_label}</em>
              {workflowSummary.primary_action.kind === 'download' ? (
                <a
                  className="btn btn-secondary btn-sm"
                  href="/api/system/fundamentals-priority-fill"
                  download="fundamentals_priority_fill.csv"
                >
                  {workflowSummary.primary_action.label}
                </a>
              ) : workflowSummary.primary_action.kind === 'api' ? (
                <button className="btn btn-primary btn-sm" onClick={onPreviewMerge} disabled={merging}>
                  {merging ? '處理中…' : workflowSummary.primary_action.label}
                </button>
              ) : (
                <small>{workflowSummary.primary_action.command}</small>
              )}
            </div>
          </div>
          <div className="fundamentals-workflow-steps">
            {workflowSummary.checklist.map(step => (
              <div className={`fundamentals-workflow-step ${step.status}`} key={step.key}>
                <span>{step.status === 'done' ? '完成' : step.status === 'todo' ? '待辦' : '等待'}</span>
                <strong>{step.label}</strong>
                <p>{step.detail}</p>
              </div>
            ))}
          </div>
          {workflowSummary.focus_targets.length > 0 && (
            <div className="fundamentals-workflow-focus">
              <span>本輪先補</span>
              {workflowSummary.focus_targets.slice(0, 5).map(target => (
                <strong key={target.code}>
                  {target.name} <em>{target.code}</em>
                </strong>
              ))}
            </div>
          )}
        </div>
      )}
      {(nextFillTargets.length > 0 || missingFields.length > 0) && (
        <div className="fundamentals-gap-panel">
          <div className="fundamentals-gap-head">
            <div>
              <span>基本面補資料優先順序</span>
              <strong>{nextFillTargets.length > 0 ? `${nextFillTargets.length} 檔優先補` : '依缺欄位補齊'}</strong>
            </div>
            <a
              className="btn btn-secondary btn-sm"
              href="/api/system/fundamentals-priority-fill"
              download="fundamentals_priority_fill.csv"
            >
              下載補資料 CSV
            </a>
            <button className="btn btn-ghost btn-sm" onClick={copyFillTargets} disabled={nextFillTargets.length === 0}>
              {copiedFillTargets ? '已複製清單' : '複製補資料清單'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={onPreviewMerge} disabled={merging || !canPreviewPriorityFill}>
              {merging ? '處理中…' : '預覽合併'}
            </button>
            <button className="btn btn-primary btn-sm" onClick={onApplyMerge} disabled={merging || !canMergePriorityFill}>
              合併匯入
            </button>
          </div>
          {fillReadiness && (
            <div className={`fundamentals-readiness ${readinessClass}`}>
              <strong>
                {fillReadiness.status === 'ready_to_preview'
                  ? '補資料 CSV 可預覽但尚不可合併'
                  : fillReadiness.status === 'ready_to_merge'
                    ? '補資料 CSV 已可合併'
                  : fillReadiness.status === 'invalid'
                    ? '補資料 CSV 需要修正'
                    : '補資料 CSV 尚未可匯入'}
              </strong>
              <span>{fillReadiness.message}</span>
              <em>{fillReadiness.suggested_action}</em>
            </div>
          )}
          {priorityValidationIssues.length > 0 && (
            <div className="fundamentals-validation-issues">
              <strong>CSV 檢查提醒</strong>
              {priorityValidationIssues.map((issue, index) => (
                <div key={`${issue.kind}-${issue.row_number}-${issue.field}-${index}`}>
                  <span>{issue.kind} · 第 {issue.row_number} 列 {issue.code ? `· ${issue.code}` : ''}</span>
                  <small>{labels[issue.field ?? ''] ?? issue.field ?? '欄位'}：{issue.value ?? ''} {issue.message}</small>
                </div>
              ))}
            </div>
          )}
          {fillGuide && (
            <div className="fundamentals-fill-guide">
              <div>
                <span>下一步</span>
                <strong>{fillGuide.next_action_label}</strong>
              </div>
              <div>
                <span>可評分</span>
                <strong>{fillGuide.complete_ready_count}</strong>
              </div>
              <div>
                <span>部分填寫</span>
                <strong>{fillGuide.partial_count}</strong>
              </div>
              <div>
                <span>空白</span>
                <strong>{fillGuide.empty_count}</strong>
              </div>
              <p>{fillGuide.format_note}</p>
              {fillGuide.warning_count > 0 && (
                <em>有 {fillGuide.warning_count} 個數值需要再確認格式。</em>
              )}
            </div>
          )}
          {mergeResult && (
            <div className={`fundamentals-merge-result ${mergeResult.dry_run ? 'preview' : 'applied'}`}>
              <strong>{mergeResult.dry_run ? '預覽結果' : '已合併匯入'}</strong>
              <span>
                更新 {mergeResult.updated_code_count} 檔 / {mergeResult.updated_field_count} 欄
                {mergeResult.added_count > 0 ? `，新增 ${mergeResult.added_count} 檔` : ''}
                {mergeResult.imported_count != null ? `，匯入 JSON ${mergeResult.imported_count} 檔` : ''}
              </span>
              <div className="fundamentals-merge-summary">
                <span>可合併 {mergeResult.complete_codes?.length ?? 0} 檔</span>
                <span>部分填寫 {mergeResult.partial_codes?.length ?? 0} 檔</span>
                <span>空白 {mergeResult.empty_codes?.length ?? 0} 檔</span>
                {(mergeResult.warning_count ?? 0) > 0 && <span>警告 {mergeResult.warning_count} 個</span>}
              </div>
              {mergeResult.blocked_reason && (
                <em>{mergeResult.blocked_reason}</em>
              )}
              {mergeResult.next_action_label && (
                <div className={`fundamentals-next-step ${mergeResult.signals_refresh_required ? 'refresh' : ''}`}>
                  <div>
                    <span>下一步</span>
                    <strong>{mergeResult.next_action_label}</strong>
                  </div>
                  {mergeResult.signals_refresh_required && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={onRunSignals}
                      disabled={signalsBusy}
                    >
                      {signalsBusy ? '重算中…' : '重新產生訊號'}
                    </button>
                  )}
                </div>
              )}
              {mergePartialRows.length > 0 && (
                <div className="fundamentals-partial-preview">
                  <strong>部分填寫仍缺欄位</strong>
                  {mergePartialRows.map(row => (
                    <div key={`${row.code}-${row.row_number}`}>
                      <span>{row.code} 已填 {row.filled_field_count}/11</span>
                      <small>還缺 {row.missing_fields.slice(0, 3).map(field => labels[field] ?? field).join('、')}{row.missing_field_count > 3 ? '…' : ''}</small>
                    </div>
                  ))}
                </div>
              )}
              {(mergeResult.buffett_preview?.length ?? 0) > 0 && (
                <div className="fundamentals-buffett-preview">
                  <strong>巴菲特試算</strong>
                  {mergeResult.buffett_preview?.slice(0, 5).map(item => (
                    <div key={item.code}>
                      <div className="fundamentals-buffett-main">
                        <span>{item.name} {item.code}</span>
                        <b className={buffettScoreClass(item.buffett_score)}>{item.buffett_score ?? 'NA'}</b>
                        <small>{item.buffett_signal || (item.buffett_data_ok ? '可評分' : '資料不足')}</small>
                      </div>
                      <div className="fundamentals-buffett-score-badges">
                        {BUFFETT_SCORE_LABELS.map(score => {
                          const value = item[score.key]
                          return (
                            <span className={buffettScoreClass(value)} key={`${item.code}-${score.key}`}>
                              {score.label} {value ?? 'NA'}
                            </span>
                          )
                        })}
                      </div>
                      {item.buffett_reason && <p>{item.buffett_reason}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {nextFillTargets.length > 0 && (
            <div className="fundamentals-fill-priority">
              <div>
                <span>優先補資料</span>
                <strong>先補前 {Math.min(10, nextFillTargets.length)} 檔，不必一次補完 74 檔</strong>
              </div>
              <p>每檔補齊 11 欄後先按「預覽合併」，確認可評分再合併匯入。</p>
            </div>
          )}
          {nextFillTargets.length > 0 && (
            <div className="fundamentals-target-list">
              {nextFillTargets.map(target => (
                <div className="fundamentals-target" key={target.code}>
                  <strong>{target.name} <em>{target.code}</em></strong>
                  <span>{target.priority_reason} · 缺 {target.missing_count} 欄</span>
                  <p>{target.missing_field_labels.slice(0, 3).join('、')}{target.missing_count > 3 ? '…' : ''}</p>
                </div>
              ))}
            </div>
          )}
          {missingFields.length > 0 && (
            <div className="fundamentals-missing-fields">
              {missingFields.map(([field, count]) => (
                <span key={field}>{labels[field] ?? field} {count}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ChangeReport({ summary }: { summary: SignalsSummary | null }) {
  const report = summary?.change_report
  if (!report) return null

  const newItems = report.new_recommendations.slice(0, 5)
  const removedItems = report.removed_recommendations.slice(0, 5)
  const changedItems = report.signal_changes.slice(0, 6)

  return (
    <div className="dash-section">
      <h3 className="dash-section-title">本次變化</h3>
      <div className="change-report">
        <div className="change-report-meta">
          {report.has_previous
            ? <>與前次資料日 <strong>{report.previous_as_of ?? '—'}</strong> 比較</>
            : '尚無前次 summary，這次先建立比較基準'}
        </div>
        <div className="change-summary-grid">
          <div><span>新增推薦</span><strong>{report.summary.new_count}</strong></div>
          <div><span>移出推薦</span><strong>{report.summary.removed_count}</strong></div>
          <div><span>狀態變化</span><strong>{report.summary.changed_count}</strong></div>
        </div>
        {(newItems.length > 0 || removedItems.length > 0 || changedItems.length > 0) && (
          <div className="change-columns">
            {newItems.length > 0 && (
              <div>
                <div className="change-title">新增推薦</div>
                {newItems.map(item => (
                  <div className="change-item" key={`new-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{SIGNAL_TEXT[item.internal_signal] ?? item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
            {removedItems.length > 0 && (
              <div>
                <div className="change-title">移出推薦</div>
                {removedItems.map(item => (
                  <div className="change-item" key={`removed-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{item.no_buy_reason || SIGNAL_TEXT[item.internal_signal] || item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
            {changedItems.length > 0 && (
              <div>
                <div className="change-title">狀態變化</div>
                {changedItems.map(item => (
                  <div className="change-item" key={`changed-${item.code}`}>
                    <strong>{item.name}</strong><span>{item.code}</span>
                    <em>{SIGNAL_TEXT[item.previous_signal ?? ''] ?? item.previous_signal} → {SIGNAL_TEXT[item.internal_signal] ?? item.internal_signal}</em>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const BRIEF_BUCKETS: Array<{
  key: keyof DailyBrief['rotation_plan']
  countKey: string
  label: string
  cls: string
}> = [
  { key: 'priority_reduce', countKey: 'priority_reduce_count', label: '優先減碼', cls: 'brief-risk' },
  { key: 'entry_candidates', countKey: 'entry_candidates_count', label: '可進場', cls: 'brief-enter' },
  { key: 'continue_hold', countKey: 'continue_hold_count', label: '續抱', cls: 'brief-hold' },
  { key: 'wait_pullback', countKey: 'wait_pullback_count', label: '等回測', cls: 'brief-watch' },
  { key: 'avoid_no_chase', countKey: 'avoid_no_chase_count', label: '暫不碰', cls: 'brief-muted' },
]

const TASK_BUCKET_LABEL: Record<string, string> = {
  priority_reduce: '優先減碼',
  entry_candidates: '可進場',
  continue_hold: '續抱',
  wait_pullback: '等回測',
  avoid_no_chase: '暫不碰',
  long_watch: '長期觀察',
  unassigned_watch: '觀察',
}

function BriefStockList({
  stocks,
  onAnalysis,
}: {
  stocks: DailyBriefStock[]
  onAnalysis?: (code: string) => void
}) {
  if (!stocks.length) return <span className="brief-empty">—</span>
  return (
    <div className="brief-stock-list">
      {stocks.slice(0, 4).map(stock => (
        <button
          type="button"
          className="brief-stock-token"
          key={stock.code}
          onClick={() => onAnalysis?.(stock.code)}
          disabled={!onAnalysis}
          title={onAnalysis ? '查看技術分析與線圖' : undefined}
        >
          <strong>{stock.name}</strong>
          <em>{stock.code}</em>
        </button>
      ))}
      {stocks.length > 4 && <span className="brief-more">+{stocks.length - 4}</span>}
    </div>
  )
}

function TomorrowTaskList({
  tasks,
  onAnalysis,
}: {
  tasks: DailyBriefTask[]
  onAnalysis?: (code: string) => void
}) {
  const topTasks = tasks.slice(0, 6)
  if (!topTasks.length) {
    return <p className="empty-hint">尚無明日任務，請先重新產生訊號。</p>
  }
  return (
    <div className="brief-task-list">
      {topTasks.map(task => (
        <button
          type="button"
          className={`brief-task${onAnalysis ? ' brief-task-clickable' : ''}`}
          key={`${task.bucket}-${task.code}`}
          onClick={() => onAnalysis?.(task.code)}
          disabled={!onAnalysis}
          title={onAnalysis ? '查看技術分析與線圖' : undefined}
        >
          <div className="brief-task-main">
            <span className={`brief-badge ${task.bucket}`}>{TASK_BUCKET_LABEL[task.bucket] ?? task.bucket}</span>
            <strong>{task.name} <em>{task.code}</em></strong>
            <p>{task.reason || task.trigger_action}</p>
          </div>
          <div className="brief-task-plan">
            <span>觀察：{task.watch_price || '—'}</span>
            <span>進場：{task.entry_plan || '—'}</span>
            <span>失效：{task.invalidation || task.stop_plan || '—'}</span>
          </div>
        </button>
      ))}
    </div>
  )
}

const MANUAL_REVIEW_SUMMARY_KEYS: Array<{ key: string; label: string }> = [
  { key: 'entry_candidates_count', label: '可小試' },
  { key: 'continue_hold_count', label: '續抱' },
  { key: 'wait_pullback_count', label: '等回測' },
  { key: 'avoid_no_chase_count', label: '先觀察' },
  { key: 'missing_count', label: '缺資料' },
]

function ManualReviewStockCard({
  item,
  onAnalysis,
}: {
  item: ManualWatchlistReviewItem
  onAnalysis?: (code: string) => void
}) {
  const clickable = Boolean(onAnalysis && item.found)
  return (
    <button
      type="button"
      className={`manual-review-item ${item.bucket}${item.found ? '' : ' missing'}`}
      onClick={() => clickable && onAnalysis?.(item.code)}
      disabled={!clickable}
      title={clickable ? '查看技術分析與線圖' : undefined}
    >
      <div className="manual-review-main">
        <span className={`brief-badge ${item.bucket}`}>{TASK_BUCKET_LABEL[item.bucket] ?? item.decision_hint ?? item.bucket}</span>
        <strong>{item.name || item.code} <em>{item.code}</em></strong>
        <p>{item.reason || item.decision_hint || '依人工盤後筆記列入觀察'}</p>
      </div>
      <div className="manual-review-plan">
        <span>觀察：{item.watch_price || item.daily_key_price || '—'}</span>
        <span>進場：{item.entry_plan || item.price_plan_note || '—'}</span>
        <span>失效：{item.invalidation || item.daily_invalidation || item.stop_plan || '—'}</span>
      </div>
    </button>
  )
}

function ManualWatchlistReviewPanel({
  review,
  onAnalysis,
}: {
  review: ManualWatchlistReview | null
  onAnalysis?: (code: string) => void
}) {
  if (!review?.items?.length) return null

  const playbook = review.manual_playbook
  const visibleItems = review.items.slice(0, 9)
  const focusSectors = playbook?.focus_sectors?.slice(0, 4) ?? []

  return (
    <div className="manual-review-panel">
      <div className="manual-review-head">
        <div>
          <span className="old-wang-market-label">盤後觀察股校正</span>
          <strong>{review.manual_note_title || '依人工盤後筆記校正觀察清單'}</strong>
          <em>
            資料日 {review.as_of ?? '—'}
            {playbook?.target_level ? ` · 水位 ${playbook.target_level}` : ''}
            {playbook?.target_position_pct != null ? ` · 約 ${playbook.target_position_pct}%` : ''}
          </em>
        </div>
        {focusSectors.length > 0 && (
          <div className="manual-review-sectors">
            {focusSectors.map(sector => <span key={sector}>{sector}</span>)}
          </div>
        )}
      </div>
      <div className="manual-review-summary">
        {MANUAL_REVIEW_SUMMARY_KEYS.map(item => (
          <span key={item.key}>
            {item.label}
            <strong>{review.summary?.[item.key] ?? 0}</strong>
          </span>
        ))}
      </div>
      <div className="manual-review-grid">
        {visibleItems.map(item => (
          <ManualReviewStockCard
            key={`${item.bucket}-${item.code}`}
            item={item}
            onAnalysis={onAnalysis}
          />
        ))}
      </div>
      {review.items.length > visibleItems.length && (
        <div className="manual-review-more">尚有 {review.items.length - visibleItems.length} 檔可在詳細報表查看</div>
      )}
    </div>
  )
}

function DailyBriefBox({
  brief,
  manualReview,
  running,
  onNavigateAnalysis,
}: {
  brief: DailyBrief | null
  manualReview: ManualWatchlistReview | null
  running: boolean
  onNavigateAnalysis?: (code: string) => void
}) {
  if (!brief && !running) return null

  const dataStatus = brief?.data_status
  const guidance = brief?.position_guidance
  const rotation = brief?.rotation_plan
  const missingStocks = dataStatus?.missing_stocks ?? []
  const embeddedManualReview = brief?.manual_watchlist_review
    ? {
      as_of: brief.as_of,
      generated_at: brief.generated_at,
      manual_note_title: brief.manual_note_title,
      position_guidance: brief.position_guidance,
      manual_playbook: brief.manual_playbook ?? null,
      items: brief.manual_watchlist_review.items,
      summary: brief.manual_watchlist_review.summary,
    }
    : null
  const effectiveManualReview = manualReview ?? embeddedManualReview

  return (
    <div className="dash-section">
      <div className="dash-section-heading">
        <h3 className="dash-section-title">每日作戰表</h3>
        {brief && (
          <span className="brief-meta">
            as_of <strong>{brief.as_of ?? '—'}</strong>
            {brief.generated_at ? ` · ${brief.generated_at.slice(0, 16).replace('T', ' ')}` : ''}
          </span>
        )}
      </div>

      {running && (
        <div className="alert alert-running" role="status" style={{ marginBottom: 12 }}>
          <div className="alert-title">
            <span className="spinner" aria-hidden="true" />
            每日作戰表正在重新整理…
          </div>
        </div>
      )}

      {brief ? (
        <div className="daily-brief-card">
          <div className="brief-topline">
            <div className={`brief-status ${dataStatus?.is_stale ? 'stale' : 'fresh'}`}>
              <span>{dataStatus?.status_label ?? '資料狀態'}</span>
              <strong>{dataStatus?.last_data_as_of ?? '—'}</strong>
              <em>{dataStatus?.message ?? ''}</em>
            </div>
            <div className={`brief-position ${guidance?.risk_level ?? 'neutral'}`}>
              <span>建議水位</span>
              <strong>{guidance?.target_level ?? '依系統水位'}</strong>
              <em>{guidance?.reason || guidance?.old_wang_market_reason || '依大盤濾網與個股訊號調整'}</em>
            </div>
          </div>

          {dataStatus?.update_required && (
            <div className="brief-warning">
              這份作戰表需要更新：{dataStatus.update_command}
            </div>
          )}

          {dataStatus && (
            <div className="brief-data-strip">
              <span>覆蓋 <strong>{dataStatus.data_ok_count}/{dataStatus.universe_size}</strong></span>
              <span>完整率 <strong>{dataStatus.data_ok_pct.toFixed(1)}%</strong></span>
              {dataStatus.data_missing_count > 0 && (
                <span className="brief-data-warning">缺資料 {dataStatus.data_missing_count}</span>
              )}
            </div>
          )}

          {missingStocks.length > 0 && (
            <div className="brief-missing-list">
              {missingStocks.slice(0, 6).map((stock, idx) => (
                <span key={`${stock.code ?? 'missing'}-${idx}`}>
                  <strong>{stock.name ?? stock.code ?? '未知'}</strong>
                  {stock.code && <em>{stock.code}</em>}
                  {stock.reason && <small>{stock.reason}</small>}
                </span>
              ))}
              {missingStocks.length > 6 && <span className="brief-more">+{missingStocks.length - 6}</span>}
            </div>
          )}

          <ManualWatchlistReviewPanel
            review={effectiveManualReview}
            onAnalysis={onNavigateAnalysis}
          />

          {rotation && (
            <div className="brief-rotation-grid">
              {BRIEF_BUCKETS.map(bucket => {
                const stocks = rotation[bucket.key]
                if (!Array.isArray(stocks)) return null
                const count = rotation.summary?.[bucket.countKey] ?? stocks.length
	                return (
	                  <div className={`brief-rotation-card ${bucket.cls}`} key={bucket.key}>
	                    <span>{bucket.label}</span>
	                    <strong>{count}</strong>
	                    <BriefStockList stocks={stocks} onAnalysis={onNavigateAnalysis} />
	                  </div>
	                )
              })}
            </div>
          )}

          {brief.tomorrow_checklist?.length > 0 && (
            <div className="brief-checklist">
              {brief.tomorrow_checklist.slice(0, 6).map(item => (
                <span key={item}>{item}</span>
              ))}
            </div>
          )}

          <TomorrowTaskList tasks={brief.tomorrow_tasks ?? []} onAnalysis={onNavigateAnalysis} />
        </div>
      ) : (
        <p className="empty-hint">尚無每日作戰表，完成訊號計算後會自動產生。</p>
      )}
    </div>
  )
}

function WorkflowStatusBox({
  workflow,
  busy,
  onUpdateData,
  onRunSignals,
  onFocusMarketNote,
  onFocusDecisionJournal,
  onFocusFundamentals,
  onNavigateUniverseReport,
  onNavigateAnalysis,
  onJournalDraft,
}: {
  workflow: WorkflowStatus | null
  busy: boolean
  onUpdateData: () => void
  onRunSignals: () => void
  onFocusMarketNote: () => void
  onFocusDecisionJournal: () => void
  onFocusFundamentals: () => void
  onNavigateUniverseReport?: (journalFilter?: 'all' | 'unrecorded' | 'recorded') => void
  onNavigateAnalysis?: (code: string) => void
  onJournalDraft: (task: WorkflowPortfolioTask) => void
}) {
  const [copiedPendingUniverse, setCopiedPendingUniverse] = useState(false)
  const [copiedWorkflowCommand, setCopiedWorkflowCommand] = useState<string | null>(null)

  if (!workflow) return null

  const visibleActions = workflow.next_actions.slice(0, 4)
  const closeChecklist = workflow.close_checklist ?? []
  const portfolioTasks = workflow.portfolio_tasks ?? []
  const metrics = workflow.workflow_metrics
  const guardrails = workflow.decision_guardrails
  const readinessReview = workflow.readiness_review
  const actionByKey = new Map(workflow.next_actions.map(action => [action.key, action]))
  const statusText: Record<string, string> = {
    ready: '可操作',
    warning: '可操作但待補',
    blocked: '先處理前置',
    running: '執行中',
  }
  const journalTodayCount = metrics?.decision_journal_today_count ?? 0
  const journalMissingCount = metrics?.portfolio_tasks_without_journal_count ?? 0
  const reportActionableCount = metrics?.universe_actionable_count ?? 0
  const reportJournalMissingCount = metrics?.universe_actionable_without_journal_count ?? 0
  const pendingUniverseItems = Array.isArray(workflow.checks?.universe_report_journal?.missing_actionable_items)
    ? workflow.checks.universe_report_journal.missing_actionable_items.filter(isWorkflowUniversePendingItem)
    : []

  const handleCopyPendingUniverse = async () => {
    const rows = pendingUniverseItems.map((item, index) => {
      const detail = [
        item.label || item.action,
        item.key_price ? `關鍵 ${item.key_price}` : '',
        item.invalidation ? `失效 ${item.invalidation}` : '',
        item.reason,
      ].filter(Boolean).join(' / ')
      return `${index + 1}. ${item.name} ${item.code} - ${detail}`
    })
    const text = [
      `候選股待補復盤 - ${workflow.data_as_of ?? '未指定資料日'}`,
      `待補 ${pendingUniverseItems.length} 檔`,
      rows.length > 0 ? rows.join('\n') : '目前沒有待補復盤。',
    ].join('\n')

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedPendingUniverse(true)
      window.setTimeout(() => setCopiedPendingUniverse(false), 1600)
    } catch (error) {
      console.error('copy pending universe review failed', error)
    }
  }

  const copyWorkflowCommand = async (key: string, text: string) => {
    if (!text) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedWorkflowCommand(key)
      window.setTimeout(() => setCopiedWorkflowCommand(current => current === key ? null : current), 1600)
    } catch (error) {
      console.error('copy workflow command failed', error)
    }
  }

  const actionButton = (actionType: string, compact = false) => {
    const buttonClass = compact ? 'btn btn-ghost btn-xs' : 'btn btn-secondary btn-sm'
    if (actionType === 'update_data') {
      return <button className={buttonClass} onClick={onUpdateData} disabled={busy}>更新資料</button>
    }
    if (actionType === 'run_signals') {
      return <button className={compact ? 'btn btn-ghost btn-xs' : 'btn btn-primary btn-sm'} onClick={onRunSignals} disabled={busy}>重算訊號</button>
    }
    if (actionType === 'market_note') {
      return <button className={buttonClass} onClick={onFocusMarketNote} disabled={busy}>補筆記</button>
    }
    if (actionType === 'decision_journal') {
      return <button className={buttonClass} onClick={onFocusDecisionJournal} disabled={busy}>補紀錄</button>
    }
    if (actionType === 'universe_report') {
      return <button className={buttonClass} onClick={() => onNavigateUniverseReport?.('unrecorded')} disabled={!onNavigateUniverseReport}>看報表</button>
    }
    if (actionType === 'fundamentals') {
      return <button className={buttonClass} onClick={onFocusFundamentals} disabled={busy}>看缺欄位</button>
    }
    return null
  }
  const checklistText: Record<string, string> = {
    done: '完成',
    todo: '待處理',
    blocked: '卡住',
    running: '執行中',
  }
  const readinessText: Record<string, string> = {
    ready: '就緒',
    warning: '待補',
    blocked: '卡住',
  }

  return (
    <div className={`workflow-box workflow-${workflow.overall_status}`}>
      <div className="workflow-head">
        <div>
          <span className="old-wang-market-label">PM 工作流</span>
          <strong>{workflow.headline}</strong>
          <em>資料日 {workflow.data_as_of ?? '—'} · {statusText[workflow.overall_status] ?? workflow.overall_status}</em>
        </div>
        <span className={`workflow-status ${workflow.can_trade_today ? 'ready' : 'blocked'}`}>
          {workflow.can_trade_today ? '可進行決策' : '暫停交易判斷'}
        </span>
      </div>

      {metrics && (
        <div className="workflow-metrics">
          <div className={metrics.blocker_count > 0 ? 'risk' : 'ok'}>
            <span>阻塞</span>
            <strong>{metrics.blocker_count}</strong>
          </div>
          <div className={metrics.warning_count > 0 ? 'warn' : 'ok'}>
            <span>提醒</span>
            <strong>{metrics.warning_count}</strong>
          </div>
          <div>
            <span>流程完成</span>
            <strong>{metrics.done_step_count}/6</strong>
          </div>
          <div className={metrics.portfolio_danger_count > 0 ? 'risk' : 'ok'}>
            <span>持股風險</span>
            <strong>{metrics.portfolio_danger_count}/{metrics.portfolio_task_count}</strong>
          </div>
          <div className={journalMissingCount > 0 ? 'warn' : 'ok'}>
            <span>決策紀錄</span>
            <strong>{journalTodayCount}/{metrics.portfolio_task_count}</strong>
          </div>
          <button
            type="button"
            className={reportJournalMissingCount > 0 ? 'warn workflow-metric-action' : 'ok workflow-metric-action'}
            onClick={() => onNavigateUniverseReport?.('unrecorded')}
            disabled={!onNavigateUniverseReport}
            title="前往候選股篩選報告補復盤紀錄"
          >
            <span>候選復盤</span>
            <strong>{reportActionableCount - reportJournalMissingCount}/{reportActionableCount}</strong>
          </button>
        </div>
      )}

      {pendingUniverseItems.length > 0 && (
        <div className="workflow-universe-pending">
          <div className="workflow-subhead">
            <strong>候選股待補復盤</strong>
            <div className="workflow-universe-pending-actions">
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={handleCopyPendingUniverse}
              >
                {copiedPendingUniverse ? '已複製' : '複製'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={() => onNavigateUniverseReport?.('unrecorded')}
                disabled={!onNavigateUniverseReport}
              >
                看全部
              </button>
            </div>
          </div>
          <div className="workflow-universe-pending-list">
            {pendingUniverseItems.slice(0, 3).map(item => (
              <div className="workflow-universe-pending-item" key={item.code}>
                <div>
                  <strong>{item.name} <em>{item.code}</em></strong>
                  <span>{item.label || item.action} · {item.reason}</span>
                  <small>
                    關鍵 {item.key_price ?? '—'}
                    {item.invalidation ? ` · 失效 ${item.invalidation}` : ''}
                  </small>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-xs"
                  onClick={() => onNavigateAnalysis?.(item.code)}
                  disabled={!onNavigateAnalysis}
                >
                  線圖
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {guardrails && (
        <div className={`workflow-guardrails ${guardrails.can_use_trade_outputs ? 'ready' : 'blocked'}`}>
          <strong>{guardrails.can_use_trade_outputs ? '交易輸出可使用' : '交易輸出暫停使用'}</strong>
          <p>{guardrails.message}</p>
          {guardrails.blocked_outputs.length > 0 && (
            <span>暫停：{guardrails.blocked_outputs.join('、')}</span>
          )}
          {guardrails.required_action && (
            <div className="workflow-command-line">
              <code>{guardrails.required_action}</code>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={() => copyWorkflowCommand(
                  'guardrails',
                  guardrails.required_action_copy_command || guardrails.required_action || '',
                )}
              >
                {copiedWorkflowCommand === 'guardrails' ? '已複製' : '複製'}
              </button>
            </div>
          )}
        </div>
      )}

      {readinessReview && readinessReview.sections.length > 0 && (
        <div className="workflow-readiness" aria-label="每日資料閉環">
          <div className="workflow-subhead">
            <strong>每日資料閉環</strong>
            <span>{readinessReview.overall_label}</span>
          </div>
          <div className="workflow-readiness-grid">
            {readinessReview.sections.map(section => (
              (() => {
                const linkedAction = section.next_action_key ? actionByKey.get(section.next_action_key) : undefined
                return (
                  <div
                    className={`workflow-readiness-item ${section.status} ${readinessReview.top_blocker_key === section.key ? 'top-blocker' : ''}`}
                    key={section.key}
                  >
                    <span>{readinessText[section.status] ?? section.status}</span>
                    <strong>{section.label}</strong>
                    <p>{section.message}</p>
                    {linkedAction && (
                      <div className="workflow-readiness-action">
                        {actionButton(linkedAction.action_type, true)}
                      </div>
                    )}
                  </div>
                )
              })()
            ))}
          </div>
        </div>
      )}

      {visibleActions.length > 0 ? (
        <div className="workflow-actions">
          {visibleActions.map(action => (
            <div className={`workflow-action ${action.severity}`} key={action.key}>
              <div>
                <strong>{action.title}</strong>
                <p>{action.detail}</p>
                {action.command && (
                  <div className="workflow-command-line">
                    <code>{action.command}</code>
                    <button
                      type="button"
                      className="btn btn-ghost btn-xs"
                      onClick={() => copyWorkflowCommand(action.key, action.copy_command || action.command || '')}
                    >
                      {copiedWorkflowCommand === action.key ? '已複製' : '複製'}
                    </button>
                  </div>
                )}
                {action.success_check && <small>{action.success_check}</small>}
                {action.expected_outputs && action.expected_outputs.length > 0 && (
                  <ul className="workflow-outputs">
                    {action.expected_outputs.slice(0, 4).map(output => (
                      <li key={output}>{output}</li>
                    ))}
                  </ul>
                )}
              </div>
              {actionButton(action.action_type)}
            </div>
          ))}
        </div>
      ) : (
        <p className="workflow-ready-text">今天的資料流、訊號與作戰表都已就緒。</p>
      )}

      {closeChecklist.length > 0 && (
        <div className="workflow-checklist">
          {closeChecklist.map(item => (
            <div className={`workflow-step ${item.status}`} key={item.key}>
              <span>{checklistText[item.status] ?? item.status}</span>
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
            </div>
          ))}
        </div>
      )}

      {portfolioTasks.length > 0 && (
        <div className="workflow-portfolio-tasks">
          <div className="workflow-subhead">
            <strong>持股待辦</strong>
            <span>{portfolioTasks.length} 檔</span>
          </div>
          <div className="workflow-task-list">
            {portfolioTasks.slice(0, 5).map(task => (
              <div
                className={`workflow-portfolio-task ${task.severity}`}
                key={task.code}
              >
                <div className="workflow-task-badges">
                  <span>{task.label}</span>
                  <span className={task.journal_recorded ? 'journal-done' : 'journal-missing'}>
                    {task.journal_recorded ? '已記錄' : '待記錄'}
                  </span>
                </div>
                <strong>{task.name} <em>{task.code}</em></strong>
                <p>{task.reason}</p>
                <small>
                  關鍵 {task.key_price ?? '—'}
                  {task.holding_position_pct != null ? ` · 投組 ${task.holding_position_pct.toFixed(2)}%` : ''}
                </small>
                <div className="workflow-task-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => onNavigateAnalysis?.(task.code)}
                    disabled={!onNavigateAnalysis}
                  >
                    看線圖
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-xs"
                    onClick={() => onJournalDraft(task)}
                    disabled={busy}
                  >
                    記錄
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DailyCheckBox({
  report,
  expectedDataAsOf,
}: {
  report: DailyCheckReport | null
  expectedDataAsOf?: string | null
}) {
  const [copiedActionKey, setCopiedActionKey] = useState<string | null>(null)
  const statusText: Record<string, string> = {
    ok: '正常',
    warn: '待補',
    block: '阻塞',
  }
  const actionText: Record<string, string> = {
    ok: '完成',
    warn: '待補',
    block: '阻塞',
    info: '提醒',
  }

  const copyDailyCheckAction = async (key: string, text: string) => {
    if (!text) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedActionKey(key)
      window.setTimeout(() => setCopiedActionKey(null), 1600)
    } catch (error) {
      console.error('copy daily check action failed', error)
    }
  }

  const dailyCheckActionButton = (action: DailyCheckReport['top_actions'][number]) => {
    const payload = action.action_payload
    if (!payload) return null

    if (payload.kind === 'copy_text' && payload.copy_text) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.copy_text || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製清單'}
        </button>
      )
    }
    if (payload.kind === 'command' && payload.command) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.copy_command || payload.command || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製指令'}
        </button>
      )
    }
    if (payload.kind === 'file' && payload.file_path) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.file_path || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製路徑'}
        </button>
      )
    }
    return null
  }

  if (!report) {
    return (
      <div className="daily-check-box daily-check-missing">
        <div className="daily-check-head">
          <div>
            <span className="old-wang-market-label">PM Daily Check</span>
            <strong>尚未產生每日摘要</strong>
            <em>先在後端產生 daily_check.json，Dashboard 會讀取最新快照。</em>
          </div>
          <span className="daily-check-badge warn">待產生</span>
        </div>
        <code>python3 scripts/daily_check.py --write-report</code>
      </div>
    )
  }

  const dataDateNeedsRefresh = Boolean(
    report.data_as_of
    && expectedDataAsOf
    && report.data_as_of < expectedDataAsOf
  )
  const snapshotNeedsRefresh = Boolean(report.snapshot_is_stale)
  const needsRefresh = dataDateNeedsRefresh || snapshotNeedsRefresh
  const dataRepair = report.data_repair
  const dataRepairCount = dataRepair?.total_count ?? 0

  return (
    <div className={`daily-check-box daily-check-${report.overall_status}`}>
      <div className="daily-check-head">
        <div>
          <span className="old-wang-market-label">PM Daily Check</span>
          <strong>每日摘要快照</strong>
          <em>
            摘要 {report.generated_at || '—'}
            {' '}· 資料日 {report.data_as_of || '—'}
            {report.source_report_generated_at ? ` · 來源 ${report.source_report_generated_at}` : ''}
          </em>
          {dataDateNeedsRefresh && (
            <em className="daily-check-stale">
              摘要需刷新：目前資料已到 {expectedDataAsOf}，Daily Check 仍停在 {report.data_as_of}
            </em>
          )}
          {snapshotNeedsRefresh && (
            <em className="daily-check-stale">
              {report.snapshot_stale_reason || 'Daily Check 快照需刷新。'}
              {report.snapshot_refresh_command ? ` 指令：${report.snapshot_refresh_command}` : ''}
              {report.snapshot_refresh_command && (
                <button
                  type="button"
                  className="btn btn-ghost btn-xs"
                  onClick={() => copyDailyCheckAction(
                    'snapshot_refresh',
                    report.snapshot_refresh_copy_command || report.snapshot_refresh_command || '',
                  )}
                >
                  {copiedActionKey === 'snapshot_refresh' ? '已複製' : '複製刷新指令'}
                </button>
              )}
            </em>
          )}
        </div>
        <span className={`daily-check-badge ${needsRefresh ? 'warn' : report.overall_status}`}>
          {needsRefresh ? '需刷新' : (statusText[report.overall_status] ?? report.overall_status)}
        </span>
      </div>

      <div className="daily-check-summary-grid">
        <div className={report.can_use_trade_outputs ? 'ok' : 'block'}>
          <span>交易輸出</span>
          <strong>{report.can_use_trade_outputs ? '可使用' : '暫停'}</strong>
        </div>
        <div className={report.exit_code === 0 ? 'ok' : 'warn'}>
          <span>檢查代碼</span>
          <strong>{report.exit_code}</strong>
        </div>
        <div className={report.top_actions.length > 0 ? 'warn' : 'ok'}>
          <span>Top 待辦</span>
          <strong>{report.top_actions.length}</strong>
        </div>
        <div className={dataRepairCount > 0 ? 'warn' : 'ok'}>
          <span>資料修復</span>
          <strong>{dataRepairCount}</strong>
        </div>
      </div>

      {dataRepair && dataRepair.total_count > 0 && (
        <div className="daily-check-repair-strip">
          <div>
            <strong>追蹤股日線需修復</strong>
            <span>
              缺日線 {dataRepair.no_data_count} 檔 / 資料不足 {dataRepair.insufficient_count} 檔
            </span>
          </div>
          <div className="daily-check-repair-list">
            {dataRepair.top_items.slice(0, 4).map(item => (
              <span key={item.code}>
                {item.name || item.code}
                <em>{item.code}</em>
                <small>{item.status_label} · {item.row_count}/{item.required_rows}</small>
              </span>
            ))}
          </div>
        </div>
      )}

      {report.top_actions.length > 0 ? (
        <div className="daily-check-action-list">
          {report.top_actions.slice(0, 3).map(action => (
            <div className={`daily-check-action ${action.status}`} key={action.key}>
              <span>{actionText[action.status] ?? action.status}</span>
              <strong>{action.title}</strong>
              <p>{action.message}</p>
              <small>{action.next_action}</small>
              {action.action_payload?.expected_outputs && action.action_payload.expected_outputs.length > 0 && (
                <ul className="daily-check-outputs">
                  {action.action_payload.expected_outputs.slice(0, 4).map(output => (
                    <li key={output}>{output}</li>
                  ))}
                </ul>
              )}
              {dailyCheckActionButton(action)}
            </div>
          ))}
        </div>
      ) : (
        <p className="workflow-ready-text">目前沒有 PM 優先待辦。</p>
      )}
    </div>
  )
}

function UpdateWorkflowBox({ workflow }: { workflow: UpdateWorkflowStatus | null }) {
  const [copied, setCopied] = useState(false)
  const statusText: Record<string, string> = {
    ready: '完成',
    action_required: '待處理',
    blocked: '阻塞',
  }
  const stepText: Record<string, string> = {
    done: '完成',
    warning: '提醒',
    blocked: '阻塞',
    running: '執行中',
  }

  const copyCommand = async () => {
    const command = workflow?.next_action?.copy_command || workflow?.next_action?.command
    if (!command) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(command)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = command
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch (error) {
      console.error('copy update workflow command failed', error)
    }
  }

  if (!workflow) {
    return (
      <div className="daily-check-box daily-check-missing">
        <div className="daily-check-head">
          <div>
            <span className="old-wang-market-label">Update Workflow</span>
            <strong>每日更新流程尚未讀取</strong>
            <em>重新整理 Dashboard 後會顯示目前卡在哪一步。</em>
          </div>
          <span className="daily-check-badge warn">待讀取</span>
        </div>
      </div>
    )
  }

  const badgeClass = workflow.overall_status === 'ready'
    ? 'ok'
    : workflow.overall_status === 'blocked' ? 'block' : 'warn'

  return (
    <div className={`daily-check-box daily-check-${badgeClass}`}>
      <div className="daily-check-head">
        <div>
          <span className="old-wang-market-label">Update Workflow</span>
          <strong>每日更新流程</strong>
          <em>{workflow.headline}</em>
          {workflow.next_action && (
            <em className="daily-check-stale">
              下一步：{workflow.next_action.title}
              {workflow.next_action.command ? ` · ${workflow.next_action.command}` : ''}
            </em>
          )}
        </div>
        <span className={`daily-check-badge ${badgeClass}`}>
          {statusText[workflow.overall_status] ?? workflow.overall_status}
        </span>
      </div>

      <div className="daily-check-summary-grid">
        <div className={workflow.can_use_trade_outputs ? 'ok' : 'block'}>
          <span>交易輸出</span>
          <strong>{workflow.can_use_trade_outputs ? '可使用' : '暫停'}</strong>
        </div>
        {workflow.steps.map(step => (
          <div className={step.status === 'done' ? 'ok' : step.status === 'blocked' ? 'block' : 'warn'} key={step.key}>
            <span>{step.label}</span>
            <strong>{stepText[step.status] ?? step.status}</strong>
          </div>
        ))}
      </div>

      {workflow.next_action && (
        <div className="daily-check-action-list">
          <div className={`daily-check-action ${workflow.overall_status === 'blocked' ? 'block' : 'warn'}`}>
            <span>{workflow.next_action.action_type === 'wait' ? '等待' : '下一步'}</span>
            <strong>{workflow.next_action.title}</strong>
            <p>{workflow.next_action.detail}</p>
            {workflow.next_action.command && <small>{workflow.next_action.command}</small>}
            {workflow.next_action.expected_outputs.length > 0 && (
              <ul className="workflow-outputs">
                {workflow.next_action.expected_outputs.slice(0, 6).map(output => (
                  <li key={output}>{output}</li>
                ))}
              </ul>
            )}
            {workflow.next_action.command && (
              <button className="btn btn-ghost btn-xs" onClick={copyCommand}>
                {copied ? '已複製' : '複製指令'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function PmWorklistBox({
  worklist,
  busy,
  universeReviewWorkflow,
  onFocusFundamentals,
  onFocusDecisionJournal,
  onFocusDailyCheck,
  onRunUniverseReviewBatch,
}: {
  worklist: PmWorklist | null
  busy: boolean
  universeReviewWorkflow: UniverseReportReviewWorkflow | null
  onFocusFundamentals: () => void
  onFocusDecisionJournal: () => void
  onFocusDailyCheck: () => void
  onRunUniverseReviewBatch: (date?: string | null, limit?: number) => Promise<void>
}) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [runningKey, setRunningKey] = useState<string | null>(null)
  if (!worklist) return null
  type WorklistItem = PmWorklist['items'][number]

  const copyCommand = async (key: string, command: string) => {
    if (!command) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(command)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = command
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey(null), 1600)
    } catch (error) {
      console.error('copy pm command failed', error)
    }
  }

  const runUniverseReviewBatch = async (item: WorklistItem) => {
    const missingCount = universeReviewWorkflow?.missing_count ?? 0
    const limit = item.action_payload?.limit ?? Math.min(10, Math.max(1, missingCount || 10))
    const reviewDate = item.action_payload?.date ?? universeReviewWorkflow?.as_of ?? null
    const confirmMessage = item.action_payload?.confirm_message
      ?? `將從候選股報表批次建立前 ${limit} 筆復盤紀錄。這只會寫入決策日誌，不會修改交易紀錄、持倉或現金。是否繼續？`
    const ok = window.confirm(confirmMessage)
    if (!ok) return
    setRunningKey(item.key)
    try {
      await onRunUniverseReviewBatch(reviewDate, limit)
    } catch (error) {
      console.error('run universe review batch failed', error)
    } finally {
      setRunningKey(null)
    }
  }

  const copyValueForItem = (item: WorklistItem): string => {
    const payload = item.action_payload
    if (payload?.kind === 'api') return ''
    if (payload?.kind === 'copy_text') return payload.copy_text || ''
    return payload?.copy_command || payload?.command || item.command || ''
  }

  const handleItemAction = async (item: WorklistItem) => {
    const payload = item.action_payload
    const copyValue = copyValueForItem(item)

    if (payload?.kind === 'api' && payload.endpoint === '/api/decision-journal/from-universe-report') {
      await runUniverseReviewBatch(item)
      return
    }

    if (payload?.kind === 'api') {
      if (payload.endpoint === '/api/system/fundamentals-priority-fill/merge') {
        onFocusFundamentals()
        return
      }
      onFocusDailyCheck()
      return
    }

    if (payload?.kind === 'command' || payload?.kind === 'copy_text' || copyValue) {
      await copyCommand(item.key, copyValue)
      return
    }

    if (item.action_type === 'fundamentals') {
      onFocusFundamentals()
      return
    }

    if (item.action_type === 'decision_journal') {
      onFocusDecisionJournal()
      return
    }

    onFocusDailyCheck()
  }

  const actionButton = (item: WorklistItem) => {
    const hasDirectAction = Boolean(
      copyValueForItem(item)
      || item.action_type === 'fundamentals'
      || item.action_type === 'decision_journal'
      || item.action_type === 'daily_check'
      || item.action_payload?.kind === 'api'
    )
    const buttonClass = item.action_type === 'daily_check' ? 'btn btn-ghost btn-xs' : 'btn btn-secondary btn-xs'
    const label = runningKey === item.key
      ? '處理中...'
      : copiedKey === item.key ? '已複製' : item.action_label || '查看'
    return (
      <button
        className={buttonClass}
        onClick={() => { void handleItemAction(item) }}
        disabled={busy || runningKey === item.key || !hasDirectAction}
      >
        {label}
      </button>
    )
  }

  const worklistGroupForItem = (item: WorklistItem) => {
    if (item.severity === 'danger' || item.key === 'update_workflow' || item.action_type === 'data_repair') {
      return { key: 'blockers', label: '阻塞 / 資料修復' }
    }
    if (item.action_type === 'decision_journal') {
      return { key: 'review', label: '候選復盤' }
    }
    if (item.action_type === 'fundamentals') {
      return { key: 'fundamentals', label: '基本面' }
    }
    if (item.action_type === 'daily_check') {
      return { key: 'daily_check', label: 'Daily Check' }
    }
    return { key: 'maintenance', label: '維護' }
  }

  const primaryAction = worklist.primary_action ?? worklist.items[0] ?? null
  const secondaryItems = worklist.items
    .filter(item => item.key !== primaryAction?.key)
  const groupedSecondaryItems = secondaryItems.reduce<Array<{ key: string; label: string; items: WorklistItem[] }>>((groups, item) => {
    const group = worklistGroupForItem(item)
    const existing = groups.find(candidate => candidate.key === group.key)
    if (existing) {
      existing.items.push(item)
    } else {
      groups.push({ ...group, items: [item] })
    }
    return groups
  }, [])

  return (
    <div className={`pm-worklist-box ${worklist.overall_status}`}>
      <div className="pm-worklist-head">
        <div>
          <span className="old-wang-market-label">PM Worklist</span>
          <strong>{worklist.headline}</strong>
          <em>更新 {worklist.generated_at?.slice(0, 16).replace('T', ' ') || '—'}</em>
        </div>
        <span>{worklist.items.length > 0 ? `${worklist.items.length} 件` : '清空'}</span>
      </div>
      {primaryAction ? (
        <>
          <div className={`pm-worklist-primary ${primaryAction.severity}`}>
            <div className="pm-worklist-primary-main">
              <div>
                <span>現在先處理</span>
                <strong>{primaryAction.title}</strong>
                <p>{primaryAction.detail}</p>
              </div>
              <div className="pm-worklist-primary-action">
                <em>{primaryAction.metric}</em>
                {actionButton(primaryAction)}
              </div>
            </div>
            {primaryAction.action_payload?.expected_outputs && primaryAction.action_payload.expected_outputs.length > 0 && (
              <ul className="workflow-outputs">
                {primaryAction.action_payload.expected_outputs.slice(0, 6).map(output => (
                  <li key={output}>{output}</li>
                ))}
              </ul>
            )}
            {primaryAction.focus_codes.length > 0 && (
              <div className="pm-worklist-codes">
                {primaryAction.focus_codes.slice(0, 6).map(code => <span key={code}>{code}</span>)}
              </div>
            )}
          </div>
          {groupedSecondaryItems.length > 0 && (
            <div className="pm-worklist-groups">
              {groupedSecondaryItems.map(group => (
                <div className="pm-worklist-group" key={group.key}>
                  <div className="pm-worklist-group-head">
                    <strong>{group.label}</strong>
                    <span>{group.items.length} 件</span>
                  </div>
                  <div className="pm-worklist-grid">
                    {group.items.map((item, index) => (
                      <div className={`pm-worklist-item ${item.severity}`} key={item.key}>
                        <div className="pm-worklist-item-top">
                          <span>#{index + 1}</span>
                          <em>{item.metric}</em>
                        </div>
                        <strong>{item.title}</strong>
                        <p>{item.detail}</p>
                        {item.action_payload?.expected_outputs && item.action_payload.expected_outputs.length > 0 && (
                          <ul className="workflow-outputs">
                            {item.action_payload.expected_outputs.slice(0, 4).map(output => (
                              <li key={output}>{output}</li>
                            ))}
                          </ul>
                        )}
                        {item.action_payload?.preview_items && item.action_payload.preview_items.length > 0 && (
                          <div className="pm-worklist-codes">
                            {item.action_payload.preview_items.slice(0, 5).map(label => <span key={label}>{label}</span>)}
                          </div>
                        )}
                        {!item.action_payload?.preview_items?.length && item.focus_codes.length > 0 && (
                          <div className="pm-worklist-codes">
                            {item.focus_codes.slice(0, 5).map(code => <span key={code}>{code}</span>)}
                          </div>
                        )}
                        <div className="pm-worklist-item-action">
                          {actionButton(item)}
                          <small>{item.source}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="workflow-ready-text">目前沒有 PM 待辦，資料流與復盤工作都已收斂。</p>
      )}
    </div>
  )
}

function DecisionConsole({
  dataStatus,
  updateWorkflow,
  worklist,
  dailyBrief,
  workflow,
  busy,
  onFocusFundamentals,
  onFocusDecisionJournal,
  onFocusDailyCheck,
  onFocusMarketNote,
  onNavigateAnalysis,
}: {
  dataStatus: DataStatus | null
  updateWorkflow: UpdateWorkflowStatus | null
  worklist: PmWorklist | null
  dailyBrief: DailyBrief | null
  workflow: WorkflowStatus | null
  busy: boolean
  onFocusFundamentals: () => void
  onFocusDecisionJournal: () => void
  onFocusDailyCheck: () => void
  onFocusMarketNote: () => void
  onNavigateAnalysis?: (code: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const primaryAction = worklist?.primary_action ?? worklist?.items?.[0] ?? null
  const dataAsOf = workflow?.data_as_of ?? dailyBrief?.as_of ?? dataStatus?.last_data_as_of ?? null
  const rawAsOf = dataStatus?.raw_ohlcv_as_of ?? null
  const canUseTradeOutputs = updateWorkflow?.can_use_trade_outputs ?? workflow?.can_trade_today ?? false
  const isBlocked = updateWorkflow?.overall_status === 'blocked' || workflow?.overall_status === 'blocked' || dataStatus?.is_stale
  const statusLabel = isBlocked ? '需處理' : canUseTradeOutputs ? '可判斷' : '待確認'
  const statusClass = isBlocked ? 'blocked' : canUseTradeOutputs ? 'ready' : 'warning'
  const marketNoteStatus = dailyBrief?.manual_note_status
  const positionGuidance = dailyBrief?.position_guidance
  const playbook = dailyBrief?.manual_playbook
  const focusSectors = playbook?.focus_sectors?.slice(0, 4) ?? []
  const todayFocus = worklist?.today_focus ?? []
  const portfolioFocus = todayFocus.filter(item => item.category === 'portfolio_risk').slice(0, 3)
  const followupFocus = todayFocus.filter(item => item.category !== 'portfolio_risk').slice(0, 3)

  const copyText = async (value: string) => {
    if (!value) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = value
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch (error) {
      console.error('copy decision console action failed', error)
    }
  }

  const runPrimaryAction = () => {
    if (!primaryAction) return
    const payload = primaryAction.action_payload
    const command = payload?.copy_command || payload?.copy_text || primaryAction.command
    if (payload?.kind === 'command' || payload?.kind === 'copy_text' || command) {
      void copyText(command || '')
      return
    }
    if (primaryAction.action_type === 'fundamentals') {
      onFocusFundamentals()
      return
    }
    if (primaryAction.action_type === 'decision_journal') {
      onFocusDecisionJournal()
      return
    }
    if (primaryAction.action_type === 'daily_check') {
      onFocusDailyCheck()
      return
    }
    onFocusDailyCheck()
  }

  return (
    <section className={`decision-console ${statusClass}`} aria-label="首頁決策工作台">
      <div className="decision-status-strip">
        <div>
          <span>資料日</span>
          <strong>{dataAsOf ?? '—'}</strong>
          {rawAsOf && rawAsOf !== dataAsOf && <em>OHLCV {rawAsOf}</em>}
        </div>
        <div>
          <span>交易輸出</span>
          <strong>{canUseTradeOutputs ? '可使用' : '暫停'}</strong>
          <em>{statusLabel}</em>
        </div>
        <div>
          <span>價格基準</span>
          <strong>{dataStatus?.price_basis_label ?? '最新收盤價'}</strong>
          <em>非即時市價</em>
        </div>
        <div>
          <span>最後更新</span>
          <strong>{dataStatus?.last_run_finished_at?.slice(0, 16).replace('T', ' ') ?? worklist?.generated_at?.slice(0, 16).replace('T', ' ') ?? '—'}</strong>
          {dataStatus?.is_stale && <em>已 {dataStatus.stale_days ?? '?'} 天未更新</em>}
        </div>
      </div>

      <div className="decision-console-grid">
        <div className={`decision-console-card primary ${primaryAction?.severity ?? statusClass}`}>
          <span>現在最該做</span>
          <strong>{primaryAction?.title ?? '目前沒有 PM 優先待辦'}</strong>
          <p>{primaryAction?.detail ?? '資料流、復盤與基本面工作目前沒有阻塞項目。'}</p>
          {primaryAction?.action_payload?.expected_outputs && primaryAction.action_payload.expected_outputs.length > 0 && (
            <ul className="decision-console-outputs">
              {primaryAction.action_payload.expected_outputs.slice(0, 4).map(output => (
                <li key={output}>{output}</li>
              ))}
            </ul>
          )}
          {primaryAction && (
            <button className="btn btn-secondary btn-sm" onClick={runPrimaryAction} disabled={busy}>
              {copied ? '已複製' : primaryAction.action_label || '處理'}
            </button>
          )}
        </div>

        <div className="decision-console-card market">
          <span>大盤姿態</span>
          <strong>{positionGuidance?.target_level ?? '待確認'}</strong>
          <p>{positionGuidance?.reason ?? updateWorkflow?.headline ?? '先完成每日資料閉環，再判讀今日盤勢。'}</p>
          <div className="decision-console-meta">
            <em>{positionGuidance?.risk_level ?? 'risk unknown'}</em>
            {marketNoteStatus?.date && <em>筆記 {marketNoteStatus.date}</em>}
            {marketNoteStatus?.is_stale && <button className="btn btn-ghost btn-xs" onClick={onFocusMarketNote}>更新筆記</button>}
          </div>
          {focusSectors.length > 0 && (
            <div className="decision-console-tags">
              {focusSectors.map(sector => <b key={sector}>{sector}</b>)}
            </div>
          )}
        </div>

        <div className="decision-console-card focus">
          <span>今日焦點</span>
          <strong>持股風險優先</strong>
          {portfolioFocus.length > 0 ? (
            <div className="decision-focus-list">
              {portfolioFocus.map(item => (
                <button
                  key={`${item.category}-${item.source}-${item.code || item.label}`}
                  onClick={() => item.code ? onNavigateAnalysis?.(item.code) : undefined}
                  disabled={!item.code}
                  title={`${item.reason}｜${item.price_basis}`}
                >
                  <b>{item.name}{item.code ? ` ${item.code}` : ''}</b>
                  <em>{item.label}</em>
                </button>
              ))}
            </div>
          ) : (
            <p>目前沒有持股風險待辦。</p>
          )}
        </div>

        <div className="decision-console-card focus">
          <span>候選 / 復盤</span>
          <strong>{followupFocus.length > 0 ? '後端契約排序' : '先補待辦'}</strong>
          {followupFocus.length > 0 ? (
            <div className="decision-focus-list">
              {followupFocus.map(item => (
                <button
                  key={`${item.category}-${item.source}-${item.code || item.label}`}
                  onClick={() => item.category === 'entry_candidate' && item.code ? onNavigateAnalysis?.(item.code) : onFocusDecisionJournal()}
                  disabled={!item.code && item.category === 'entry_candidate'}
                  title={`${item.reason}｜${item.next_action}｜${item.price_basis}`}
                >
                  <b>{item.name}{item.code ? ` ${item.code}` : ''}</b>
                  <em>{item.label}</em>
                </button>
              ))}
            </div>
          ) : (
            <p>目前沒有候選或復盤焦點。</p>
          )}
        </div>
      </div>
    </section>
  )
}

function DataRepairQueueBox({
  universe,
  onNavigateAnalysis,
}: {
  universe: StockUniverseItem[]
  onNavigateAnalysis?: (code: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const missing = universe.filter(item => item.data_status === 'no_data')
  const insufficient = universe.filter(item => item.data_status === 'insufficient')
  const repairItems = [...missing, ...insufficient].slice(0, 8)
  const hiddenCount = missing.length + insufficient.length - repairItems.length

  const copyRepairCommand = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(DATA_REPAIR_COMMAND)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = DATA_REPAIR_COMMAND
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch (error) {
      console.error('copy data repair command failed', error)
    }
  }

  if (universe.length === 0) {
    return (
      <div className="data-repair-box data-repair-missing">
        <div className="data-repair-head">
          <div>
            <span>資料修復隊列</span>
            <strong>尚無追蹤股票資料</strong>
            <em>請先確認 backend/data/leaders.json 是否存在。</em>
          </div>
        </div>
      </div>
    )
  }

  if (repairItems.length === 0) {
    return (
      <div className="data-repair-box data-repair-ready">
        <div className="data-repair-head">
          <div>
            <span>資料修復隊列</span>
            <strong>追蹤股票日線完整</strong>
            <em>{universe.length} 檔皆已有足夠日線資料。</em>
          </div>
          <span className="data-repair-badge ok">OK</span>
        </div>
      </div>
    )
  }

  return (
    <div className="data-repair-box data-repair-warn">
      <div className="data-repair-head">
        <div>
          <span>資料修復隊列</span>
          <strong>有 {missing.length + insufficient.length} 檔需補日線</strong>
          <em>缺日線 {missing.length} 檔 / 資料不足 {insufficient.length} 檔；修完再看正式交易判斷。</em>
        </div>
        <div className="data-repair-actions">
          <button className="btn btn-primary btn-sm" onClick={copyRepairCommand}>
            {copied ? '已複製' : '複製修復指令'}
          </button>
        </div>
      </div>
      <div className="data-repair-command">
        <pre>{DATA_REPAIR_COMMAND}</pre>
      </div>
      <div className="data-repair-list">
        {repairItems.map(item => (
          <button
            type="button"
            className={`data-repair-item ${item.data_status}`}
            key={item.code}
            onClick={() => onNavigateAnalysis?.(item.code)}
            disabled={!onNavigateAnalysis}
            title={onNavigateAnalysis ? '前往技術分析頁查看單檔診斷' : undefined}
          >
            <strong>{item.name} <em>{item.code}</em></strong>
            <span>{item.data_status === 'no_data' ? '尚未回補' : '資料不足'}</span>
            <small>
              {item.row_count}/{60} 筆
              {item.last_data_as_of ? ` · 最後 ${item.last_data_as_of}` : ' · 無資料日'}
            </small>
          </button>
        ))}
      </div>
      {hiddenCount > 0 && <p className="data-repair-more">另有 {hiddenCount} 檔未列出，修復指令會一起處理全部追蹤股票。</p>}
    </div>
  )
}

function DecisionJournalBox({
  entries,
  summary,
  universeReviewWorkflow,
  defaultDate,
  filterDate,
  filterDecision,
  filterCode,
  portfolioTasks,
  busy,
  draft,
  onFilterChange,
  onJournalDraft,
  onNavigateAnalysis,
  onSave,
  onBulkCreate,
  onBulkCreateUniverseReview,
  onUpdate,
  onDelete,
}: {
  entries: DecisionJournalEntry[]
  summary: DecisionJournalSummary | null
  universeReviewWorkflow: UniverseReportReviewWorkflow | null
  defaultDate?: string | null
  filterDate: string
  filterDecision: DecisionJournalDecision | 'all'
  filterCode: string
  portfolioTasks: WorkflowPortfolioTask[]
  busy: boolean
  draft: DecisionJournalDraft | null
  onFilterChange: (date: string, decision: DecisionJournalDecision | 'all', code: string) => void
  onJournalDraft: (task: WorkflowPortfolioTask) => void
  onNavigateAnalysis?: (code: string) => void
  onSave: (entry: DecisionJournalCreate) => Promise<void>
  onBulkCreate: (date: string) => Promise<void>
  onBulkCreateUniverseReview: (date: string, limit?: number) => Promise<void>
  onUpdate: (id: string, entry: DecisionJournalCreate) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const [saving, setSaving] = useState(false)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [universeBulkSaving, setUniverseBulkSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<DecisionJournalCreate>({
    date: defaultDate || todayInputValue(),
    code: '',
    name: '',
    decision: 'hold',
    reason: '',
    price: null,
    shares: null,
    key_price: '',
    invalidation: '',
    source: 'manual',
  })

  const pendingTasks = portfolioTasks.filter(task => !task.journal_recorded)
  const activePendingTask = pendingTasks.find(task => task.code === form.code.trim())
  const nextPendingTask = activePendingTask
    ? pendingTasks.find(task => task.code !== activePendingTask.code) ?? null
    : null

  useEffect(() => {
    if (!defaultDate || editingId || draft) return
    setForm(prev => {
      if (prev.code.trim() || prev.name.trim() || prev.reason.trim()) return prev
      return { ...prev, date: defaultDate }
    })
  }, [defaultDate, editingId, draft])

  useEffect(() => {
    if (!draft) return
    setEditingId(null)
    setForm(prev => ({
      ...prev,
      date: draft.date ?? prev.date,
      code: draft.code ?? prev.code,
      name: draft.name ?? prev.name,
      decision: draft.decision ?? prev.decision,
      reason: draft.reason ?? prev.reason,
      price: draft.price ?? prev.price,
      shares: draft.shares ?? prev.shares,
      key_price: draft.key_price ?? prev.key_price,
      invalidation: draft.invalidation ?? prev.invalidation,
      source: draft.source ?? 'workflow',
    }))
  }, [draft])

  const canSave = Boolean(form.date && form.code.trim() && form.name.trim() && form.reason.trim())

  const update = <K extends keyof DecisionJournalCreate>(key: K, value: DecisionJournalCreate[K]) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const handleSubmit = async (loadNextAfterSave = false) => {
    if (!canSave || saving || busy) return
    setSaving(true)
    try {
      const payload = {
        ...form,
        code: form.code.trim(),
        name: form.name.trim(),
        reason: form.reason.trim(),
        key_price: form.key_price?.trim() || null,
        invalidation: form.invalidation?.trim() || null,
      }
      const taskToLoadNext = !editingId && loadNextAfterSave ? nextPendingTask : null
      if (editingId) {
        await onUpdate(editingId, payload)
      } else {
        await onSave(payload)
      }
      setEditingId(null)
      if (taskToLoadNext) {
        onJournalDraft(taskToLoadNext)
      } else {
        setForm(prev => ({ ...prev, reason: '', key_price: '', invalidation: '' }))
      }
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (entry: DecisionJournalEntry) => {
    setEditingId(entry.id)
    setForm({
      date: entry.date,
      code: entry.code,
      name: entry.name,
      decision: entry.decision,
      reason: entry.reason,
      price: entry.price ?? null,
      shares: entry.shares ?? null,
      key_price: entry.key_price ?? '',
      invalidation: entry.invalidation ?? '',
      source: entry.source ?? 'manual',
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setForm(prev => ({ ...prev, reason: '', key_price: '', invalidation: '' }))
  }

  const handleDelete = async (entry: DecisionJournalEntry) => {
    if (busy || deletingId) return
    const ok = window.confirm(`刪除 ${entry.name} ${entry.date} 的決策日誌？`)
    if (!ok) return
    setDeletingId(entry.id)
    try {
      await onDelete(entry.id)
    } finally {
      setDeletingId(null)
    }
  }

  const handleBulkCreate = async () => {
    if (!pendingTasks.length || bulkSaving || busy) return
    const ok = window.confirm(`將 ${pendingTasks.length} 檔持股待辦批次轉成 ${filterDate} 決策日誌？不會修改持倉或交易紀錄。`)
    if (!ok) return
    setBulkSaving(true)
    try {
      await onBulkCreate(filterDate)
    } finally {
      setBulkSaving(false)
    }
  }

  const handleUniverseBulkCreate = async () => {
    const missing = universeReviewWorkflow?.missing_count ?? 0
    if (!missing || universeBulkSaving || busy) return
    const date = universeReviewWorkflow?.as_of || filterDate
    const limit = Math.min(10, missing)
    const ok = window.confirm(`將候選股報表前 ${limit} 檔待復盤項目寫入 ${date} 決策日誌？不會修改交易紀錄、持倉或現金。`)
    if (!ok) return
    setUniverseBulkSaving(true)
    try {
      await onBulkCreateUniverseReview(date, limit)
    } finally {
      setUniverseBulkSaving(false)
    }
  }

  return (
    <div className="decision-journal-box">
      <div className="decision-journal-head">
        <div>
          <span className="old-wang-market-label">決策日誌</span>
          <strong>記錄今天為什麼買、賣、續抱或不動</strong>
        </div>
        <span>{entries.length} 筆近期紀錄</span>
      </div>

      {summary && (
        <div className="decision-journal-summary">
          <strong>{summary.date ?? '最新'}：{summary.total_count} 筆</strong>
          <div>
            {DECISION_OPTIONS.filter(option => summary.by_decision[option.key]).map(option => (
              <span key={option.key}>{option.label} {summary.by_decision[option.key]}</span>
            ))}
            {summary.total_count === 0 && <span>尚無紀錄</span>}
          </div>
        </div>
      )}

      {universeReviewWorkflow && (
        <div className={`decision-journal-universe-review ${universeReviewWorkflow.stage}`}>
          <div className="decision-journal-universe-head">
            <div>
              <span>候選股復盤</span>
              <strong>{universeReviewWorkflow.headline}</strong>
              <p>{universeReviewWorkflow.detail}</p>
            </div>
            <div>
              <em>{universeReviewWorkflow.progress_label}</em>
              {universeReviewWorkflow.stage === 'review_candidates' ? (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleUniverseBulkCreate}
                  disabled={busy || universeBulkSaving}
                >
                  {universeBulkSaving ? '記錄中…' : universeReviewWorkflow.primary_action.label}
                </button>
              ) : (
                <small>{universeReviewWorkflow.primary_action.label}</small>
              )}
            </div>
          </div>
          <div className="decision-journal-universe-steps">
            {universeReviewWorkflow.checklist.map(step => (
              <span className={step.status} key={step.key}>
                <b>{step.status === 'done' ? '完成' : step.status === 'todo' ? '待辦' : '等待'}</b>
                {step.label}
              </span>
            ))}
          </div>
          {universeReviewWorkflow.top_items.length > 0 && (
            <div className="decision-journal-universe-list">
              {universeReviewWorkflow.top_items.slice(0, 5).map(item => (
                <div key={item.code}>
                  <strong>{item.name} <em>{item.code}</em></strong>
                  <span>{item.label} · 建議 {DECISION_OPTIONS.find(option => option.key === item.decision_suggestion)?.label ?? item.decision_suggestion}</span>
                  <small>{item.reason}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="decision-journal-filters">
        <label className="form-group">
          <span>列表日期</span>
          <input
            type="date"
            value={filterDate}
            onChange={e => onFilterChange(e.target.value, filterDecision, filterCode)}
          />
        </label>
        <label className="form-group">
          <span>決策篩選</span>
          <select
            value={filterDecision}
            onChange={e => onFilterChange(filterDate, e.target.value as DecisionJournalDecision | 'all', filterCode)}
          >
            <option value="all">全部</option>
            {DECISION_OPTIONS.map(option => (
              <option value={option.key} key={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="form-group">
          <span>代號篩選</span>
          <input
            value={filterCode}
            onChange={e => onFilterChange(filterDate, filterDecision, e.target.value)}
            placeholder="例如 2330"
            inputMode="numeric"
          />
        </label>
        {defaultDate && filterDate !== defaultDate && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onFilterChange(defaultDate, filterDecision, filterCode)}
            disabled={busy}
          >
            回資料日
          </button>
        )}
      </div>

      <div className={`decision-journal-pending ${pendingTasks.length > 0 ? 'has-pending' : 'all-done'}`}>
        <div className="decision-journal-pending-head">
          <div>
            <span>今日持股待補</span>
            <strong>{pendingTasks.length > 0 ? `${pendingTasks.length} 檔尚未記錄` : '持股待辦已留紀錄'}</strong>
          </div>
          {pendingTasks.length > 0 && (
            <div className="decision-journal-pending-actions">
              <button
                type="button"
                className="btn btn-secondary btn-xs"
                onClick={() => onJournalDraft(activePendingTask ?? pendingTasks[0])}
                disabled={busy || bulkSaving}
              >
                {activePendingTask ? '重新帶入' : '帶入下一筆'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={handleBulkCreate}
                disabled={busy || bulkSaving}
              >
                {bulkSaving ? '補齊中…' : '補齊待辦'}
              </button>
            </div>
          )}
        </div>
        {pendingTasks.length > 0 ? (
          <>
            {activePendingTask && (
              <p className="decision-journal-active-task">
                正在記錄 {activePendingTask.name} {activePendingTask.code}，儲存後再帶入下一檔。
              </p>
            )}
            <div className="decision-journal-pending-list">
              {pendingTasks.slice(0, 6).map(task => (
              <div
                className={`decision-journal-pending-task${task.code === activePendingTask?.code ? ' is-active' : ''}`}
                key={task.code}
                title={`${task.reason}${task.invalidation ? `\n失效：${task.invalidation}` : ''}`}
              >
                <div>
                  <strong>{task.name}</strong>
                  <em>{task.code}</em>
                  <span>{task.label}</span>
                  <small>
                    {task.key_price ? `關鍵 ${task.key_price}` : '關鍵價待確認'}
                    {task.holding_position_pct != null && ` · 投組 ${task.holding_position_pct.toFixed(1)}%`}
                  </small>
                </div>
                <div className="decision-journal-pending-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-xs"
                    onClick={() => onJournalDraft(task)}
                    disabled={busy}
                  >
                    帶入
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => onNavigateAnalysis?.(task.code)}
                    disabled={!onNavigateAnalysis}
                  >
                    線圖
                  </button>
                </div>
              </div>
              ))}
            </div>
          </>
        ) : (
          <p>今天資料日的持股待辦都有復盤紀錄。</p>
        )}
      </div>

      <div className="decision-journal-form">
        <label className="form-group">
          <span>日期</span>
          <input type="date" value={form.date} onChange={e => update('date', e.target.value)} />
        </label>
        <label className="form-group">
          <span>代號</span>
          <input value={form.code} onChange={e => update('code', e.target.value)} placeholder="2330" />
        </label>
        <label className="form-group">
          <span>名稱</span>
          <input value={form.name} onChange={e => update('name', e.target.value)} placeholder="台積電" />
        </label>
        <label className="form-group">
          <span>決策</span>
          <select value={form.decision} onChange={e => update('decision', e.target.value as DecisionJournalDecision)}>
            {DECISION_OPTIONS.map(option => (
              <option value={option.key} key={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="form-group">
          <span>價格</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.price ?? ''}
            onChange={e => update('price', e.target.value ? Number(e.target.value) : null)}
            placeholder="選填"
          />
        </label>
        <label className="form-group">
          <span>張數/股數</span>
          <input
            type="number"
            min="0"
            step="1"
            value={form.shares ?? ''}
            onChange={e => update('shares', e.target.value ? Number(e.target.value) : null)}
            placeholder="選填"
          />
        </label>
        <label className="form-group decision-journal-wide">
          <span>理由</span>
          <textarea
            rows={2}
            value={form.reason}
            onChange={e => update('reason', e.target.value)}
            placeholder="例如：守住 MA10，但距離入場區太遠，今天不追價。"
          />
        </label>
        <label className="form-group">
          <span>關鍵價</span>
          <input value={form.key_price ?? ''} onChange={e => update('key_price', e.target.value)} placeholder="例如 MA10 2280" />
        </label>
        <label className="form-group">
          <span>失效條件</span>
          <input value={form.invalidation ?? ''} onChange={e => update('invalidation', e.target.value)} placeholder="例如 爆量跌破 MA10" />
        </label>
        <div className="decision-journal-submit">
          <button className="btn btn-primary" onClick={() => handleSubmit()} disabled={!canSave || saving || busy}>
            {saving ? '儲存中…' : editingId ? '更新決策' : '儲存決策'}
          </button>
          {!editingId && nextPendingTask && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleSubmit(true)}
              disabled={!canSave || saving || busy}
            >
              儲存並下一筆
            </button>
          )}
          {editingId && (
            <button className="btn btn-ghost btn-sm" onClick={cancelEdit} disabled={saving || busy}>
              取消編輯
            </button>
          )}
        </div>
      </div>

      {entries.length > 0 && (
        <div className="decision-journal-list">
          {entries.slice(0, 8).map(entry => (
            <div className="decision-journal-entry" key={entry.id}>
              <div className="decision-journal-entry-head">
                <span>{entry.date} · {DECISION_LABELS[entry.decision] ?? entry.decision}</span>
                <div className="decision-journal-entry-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => onNavigateAnalysis?.(entry.code)}
                    disabled={!onNavigateAnalysis}
                  >
                    線圖
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => handleEdit(entry)}
                    disabled={busy || saving}
                  >
                    編輯
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => handleDelete(entry)}
                    disabled={busy || deletingId === entry.id}
                  >
                    {deletingId === entry.id ? '刪除中' : '刪除'}
                  </button>
                </div>
              </div>
              <strong>{entry.name} <em>{entry.code}</em></strong>
              <p>{entry.reason}</p>
              {(entry.price != null || entry.shares != null || entry.key_price || entry.invalidation) && (
                <div className="decision-journal-entry-meta">
                  {entry.price != null && <span>價格 {entry.price.toLocaleString()}</span>}
                  {entry.shares != null && <span>數量 {entry.shares.toLocaleString()}</span>}
                  {entry.key_price && <span>關鍵 {entry.key_price}</span>}
                  {entry.invalidation && <span>失效 {entry.invalidation}</span>}
                </div>
              )}
              <small>
                {entry.workflow_headline ?? '未擷取工作流狀態'}
                {entry.updated_at ? ` · 已編輯 ${entry.updated_at.slice(0, 16).replace('T', ' ')}` : ''}
              </small>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RecCard({
  rec,
  onAnalysis,
}: {
  rec: StockRecommendation
  onAnalysis?: (code: string) => void
}) {
  const scoreClass = rec.score >= 85 ? 'score-high' : rec.score >= 70 ? 'score-mid' : 'score-low'
  const openAnalysis = () => onAnalysis?.(rec.stock_id)
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!onAnalysis) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openAnalysis()
    }
  }

  return (
    <div
      className={`stock-card${onAnalysis ? ' stock-card-clickable' : ''}`}
      role={onAnalysis ? 'button' : undefined}
      tabIndex={onAnalysis ? 0 : undefined}
      onClick={openAnalysis}
      onKeyDown={handleKeyDown}
      title={onAnalysis ? '查看技術分析與線圖' : undefined}
    >
      <div className="stock-card-header">
        <div>
          <span className="stock-name">{rec.name}</span>
          <span className="stock-id">{rec.stock_id}</span>
        </div>
        <span className={`score-badge ${scoreClass}`}>{rec.score.toFixed(1)} 分</span>
      </div>

      <div className="stock-price-row">
        <span className="stock-price">{rec.price.toFixed(2)}</span>
      </div>
      {rec.position_size_pct != null && (
        <div className="position-hint">
          建議倉位 <strong>{rec.position_size_pct}%</strong>
          {rec.position_size_note && <span>{rec.position_size_note}</span>}
        </div>
      )}

      {rec.old_wang_badges?.length > 0 && (
        <div className="strategy-badges" aria-label="老王策略條件">
          <span className="strategy-badge strategy-badge-source">
            老王
            {rec.old_wang_score != null ? ` ${rec.old_wang_score}` : ''}
          </span>
          {rec.old_wang_badges.map(badge => (
            <span className="strategy-badge" key={badge}>{badge}</span>
          ))}
        </div>
      )}

      {rec.recommendation_source === 'buffett' && (
        <div className="strategy-badges" aria-label="巴菲特品質價值條件">
          <span className="strategy-badge strategy-badge-source">
            巴菲特{rec.buffett_score != null ? ` ${rec.buffett_score}` : ''}
          </span>
          {rec.buffett_quality_score != null && <span className="strategy-badge">品質 {rec.buffett_quality_score}</span>}
          {rec.buffett_safety_score != null && <span className="strategy-badge">安全 {rec.buffett_safety_score}</span>}
          {rec.buffett_value_score != null && <span className="strategy-badge">估值 {rec.buffett_value_score}</span>}
        </div>
      )}

      <p className="stock-reason">{rec.reason}</p>

      <DailyChecklist items={rec.daily_checklist} compact />

      <div className="chip-grid" aria-label="籌碼摘要">
        <div className="chip-item">
          <span className="chip-label">外資</span>
          <span className="chip-value">{fmtChipLots(rec.chip.foreign_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">投信</span>
          <span className="chip-value">{fmtChipLots(rec.chip.investment_trust_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">散戶≤100張</span>
          <span className="chip-value">{fmtChipPct(rec.chip.retail_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">大戶≥400張</span>
          <span className="chip-value">{fmtChipPct(rec.chip.major_investor_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">成交量</span>
          <span className="chip-value">{fmtVolume(rec.volume)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">量比</span>
          <span className="chip-value">{rec.vol_ratio != null ? `${rec.vol_ratio.toFixed(2)}x` : '—'}</span>
        </div>
        {rec.chip.data_as_of && (
          <span className="chip-date">
            法人日 {rec.chip.data_as_of}
            {rec.chip.holder_data_as_of ? ` · 集保日 ${rec.chip.holder_data_as_of}` : ''}
          </span>
        )}
      </div>

      <div className="stock-risk">
        <span className="risk-icon">⚠</span>{rec.risk_warning}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────────────────────

interface DashboardProps {
  onNavigateAnalysis?: (code: string) => void
  onNavigateUniverseReport?: (journalFilter?: 'all' | 'unrecorded' | 'recorded') => void
}

export default function Dashboard({ onNavigateAnalysis, onNavigateUniverseReport }: DashboardProps) {
  const [status, setStatus]         = useState<SignalsStatus | null>(null)
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)
  const [fundamentalsStatus, setFundamentalsStatus] = useState<FundamentalsStatus | null>(null)
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null)
  const [updateWorkflow, setUpdateWorkflow] = useState<UpdateWorkflowStatus | null>(null)
  const [pmWorklist, setPmWorklist] = useState<PmWorklist | null>(null)
  const [dailyCheck, setDailyCheck] = useState<DailyCheckReport | null>(null)
  const [decisionJournal, setDecisionJournal] = useState<DecisionJournalEntry[]>([])
  const [decisionJournalSummary, setDecisionJournalSummary] = useState<DecisionJournalSummary | null>(null)
  const [universeReviewWorkflow, setUniverseReviewWorkflow] = useState<UniverseReportReviewWorkflow | null>(null)
  const [decisionDraft, setDecisionDraft] = useState<DecisionJournalDraft | null>(null)
  const [journalDateFilter, setJournalDateFilter] = useState('')
  const [journalDecisionFilter, setJournalDecisionFilter] = useState<DecisionJournalDecision | 'all'>('all')
  const [journalCodeFilter, setJournalCodeFilter] = useState('')
  const [summary, setSummary]       = useState<SignalsSummary | null>(null)
  const [dailyBrief, setDailyBrief] = useState<DailyBrief | null>(null)
  const [manualReview, setManualReview] = useState<ManualWatchlistReview | null>(null)
  const [universe, setUniverse]     = useState<StockUniverseItem[]>([])
  const [recs, setRecs]             = useState<StockRecommendation[]>([])
  const [strategy, setStrategy]     = useState<RecommendationStrategy>('core')
  const [loading, setLoading]       = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [running, setRunning]       = useState(false)
  const [updating, setUpdating]     = useState(false)
  const [error, setError]           = useState('')
  const [runMsg, setRunMsg]         = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [mergingFundamentals, setMergingFundamentals] = useState(false)
  const [fundamentalsMergeResult, setFundamentalsMergeResult] = useState<FundamentalsPriorityMergeResult | null>(null)
  const [noteForm, setNoteForm]     = useState<MarketNoteInput>(() => emptyMarketNoteForm())
  const [noteActionsText, setNoteActionsText] = useState('')
  const decisionJournalRef = useRef<HTMLDivElement | null>(null)
  const dailyCheckRef = useRef<HTMLDivElement | null>(null)
  const marketNoteRef = useRef<HTMLDivElement | null>(null)
  const fundamentalsRef = useRef<HTMLDivElement | null>(null)

  const focusSection = (ref: RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const journalFilters = (date: string, decision: DecisionJournalDecision | 'all', code: string) => ({
    date,
    decision: decision === 'all' ? null : decision,
    code: code.trim() || null,
  })

  const refreshDecisionJournal = async (
    workflow: WorkflowStatus | null = workflowStatus,
    date = journalDateFilter,
    decision = journalDecisionFilter,
    code = journalCodeFilter,
  ) => {
    const effectiveDate = date || workflow?.data_as_of || todayInputValue()
    const effectiveCode = code.trim()
    const [journal, journalSummary, reviewWorkflow] = await Promise.all([
      api.getDecisionJournal(20, journalFilters(effectiveDate, decision, effectiveCode)),
      api.getDecisionJournalSummary(effectiveDate),
      api.getUniverseReportReviewWorkflow(effectiveDate, 10),
    ])
    setJournalDateFilter(effectiveDate)
    setJournalDecisionFilter(decision)
    setJournalCodeFilter(effectiveCode)
    setDecisionJournal(journal)
    setDecisionJournalSummary(journalSummary)
    setUniverseReviewWorkflow(reviewWorkflow)
  }

  const fetchAll = async (nextStrategy: RecommendationStrategy = strategy) => {
    const [s, r, ds, fs, wf, uw, pm, dc, sm, brief, manual, universeItems] = await Promise.all([
      api.getSignalsStatus(),
      api.getRecommendations(nextStrategy),
      api.getDataStatus(),
      api.getFundamentalsStatus(),
      api.getWorkflowStatus(),
      api.getUpdateWorkflow(),
      api.getPmWorklist(),
      api.getDailyCheckOrNull(),
      api.getSummaryOrNull(),
      api.getDailyBriefOrNull(),
      api.getManualWatchlistReviewOrNull(),
      api.getUniverse(),
    ])
    setStatus(s)
    setRecs(r)
    setDataStatus(ds)
    setFundamentalsStatus(fs)
    setWorkflowStatus(wf)
    setUpdateWorkflow(uw)
    setPmWorklist(pm)
    setDailyCheck(dc)
    await refreshDecisionJournal(wf, journalDateFilter || wf.data_as_of || todayInputValue(), journalDecisionFilter, journalCodeFilter)
    setSummary(sm)
    setDailyBrief(brief)
    setManualReview(manual)
    setUniverse(universeItems)
    return wf
  }

  const refreshWorkflowStatusOnly = async () => {
    const [wf, uw] = await Promise.all([
      api.getWorkflowStatus(),
      api.getUpdateWorkflow(),
    ])
    setWorkflowStatus(wf)
    setUpdateWorkflow(uw)
    return wf
  }

  const handleStrategyChange = async (nextStrategy: RecommendationStrategy) => {
    if (nextStrategy === strategy) return
    setStrategy(nextStrategy)
    setRefreshing(true)
    setError('')
    try {
      const r = await api.getRecommendations(nextStrategy)
      setRecs(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : '切換推薦策略失敗')
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchAll()
      .catch(e => setError(e instanceof Error ? e.message : '載入失敗'))
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const dataDate = workflowStatus?.data_as_of
    if (!dataDate) return
    setNoteForm(prev => {
      const hasDraftContent = Boolean(
        prev.title.trim()
        || prev.headline.trim()
        || prev.position_guidance?.trim()
        || noteActionsText.trim()
      )
      if (hasDraftContent || prev.date === dataDate) return prev
      return { ...prev, date: dataDate }
    })
  }, [workflowStatus?.data_as_of, noteActionsText])

  // 當 data-status 為 running 時，每 3 秒 poll；完成後全量刷新
  useEffect(() => {
    if (dataStatus?.last_run_status !== 'running') {
      setUpdating(false)
      return
    }
    const timer = setInterval(() => {
      Promise.all([api.getDataStatus(), api.getWorkflowStatus()])
        .then(([ds, wf]) => {
          setDataStatus(ds)
          setWorkflowStatus(wf)
          if (ds.last_run_status !== 'running') {
            setUpdating(false)
            fetchAll()
              .then(wf => setRunMsg(workflowOutcomeMessage(wf)))
              .catch(() => {})
          }
        })
        .catch(() => {})
    }, 3000)
    return () => clearInterval(timer)
  }, [dataStatus?.last_run_status]) // eslint-disable-line react-hooks/exhaustive-deps

  // 訊號重算是背景執行；run_status 結束後才刷新 summary / recommendations。
  useEffect(() => {
    if (status?.run_status !== 'running') {
      setRunning(false)
      return
    }
    const timer = setInterval(() => {
      Promise.all([api.getSignalsStatus(), api.getWorkflowStatus()])
        .then(([nextStatus, wf]) => {
          setStatus(nextStatus)
          setWorkflowStatus(wf)
          if (nextStatus.run_status !== 'running') {
            setRunning(false)
            if (nextStatus.run_status === 'failed') {
              setError(nextStatus.run_error || '訊號計算失敗')
            } else {
              fetchAll()
                .then(wf => setRunMsg(workflowOutcomeMessage(wf)))
                .catch(() => setRunMsg('訊號已更新'))
            }
          }
        })
        .catch(() => {})
    }, 2000)
    return () => clearInterval(timer)
  }, [status?.run_status]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleUpdateNow = async () => {
    if (isBusy || updating || dataStatus?.last_run_status === 'running') return
    setError('')
    setRunMsg('')
    setUpdating(true)
    try {
      await api.triggerUpdateNow()
      setRunMsg('資料更新已開始，完成後會自動刷新每日資料閉環')
      await refreshWorkflowStatusOnly().catch(() => null)
      // 樂觀更新 UI 為 running 狀態，觸發 polling
      setDataStatus(prev => prev
        ? { ...prev, last_run_status: 'running', last_run_started_at: new Date().toISOString().slice(0, 19) }
        : prev
      )
    } catch (e: unknown) {
      setUpdating(false)
      // 409 = 已在執行中，仍算正常
      const msg = e instanceof Error ? e.message : '觸發更新失敗'
      if (msg.includes('已在執行中') || msg.includes('running')) {
        setDataStatus(prev => prev ? { ...prev, last_run_status: 'running' } : prev)
        setRunMsg('資料更新已在執行中，完成後會自動刷新每日資料閉環')
        await refreshWorkflowStatusOnly().catch(() => null)
      } else {
        setError(msg)
      }
    }
  }

  const handleRun = async () => {
    setRunning(true)
    setError('')
    setRunMsg('')
    try {
      await api.runSignals()
      setRunMsg('訊號計算已開始')
      setStatus(prev => prev ? { ...prev, run_status: 'running', run_error: null } : prev)
      await refreshWorkflowStatusOnly().catch(() => null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '產生訊號失敗')
      setRunning(false)
    }
  }

  const handleRefresh = async () => {
    if (refreshing || running) return
    setRefreshing(true)
    setError('')
    setRunMsg('')
    try {
      const wf = await fetchAll()
      setRunMsg(workflowOutcomeMessage(wf))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '重新整理失敗')
    } finally {
      setRefreshing(false)
    }
  }

  const handleSaveMarketNote = async (rerunSignals = false) => {
    setSavingNote(true)
    if (rerunSignals) setRunning(true)
    setError('')
    setRunMsg('')
    try {
      const payload: MarketNoteInput = {
        ...noteForm,
        title: noteForm.title.trim(),
        headline: noteForm.headline.trim(),
        position_guidance: noteForm.position_guidance?.trim() || undefined,
        market_actions: splitLines(noteActionsText),
      }
      const result = await api.saveMarketNote(payload)
      if (rerunSignals) {
        await api.runSignals()
        setRunMsg('人工筆記已儲存，訊號計算已開始')
        setStatus(prev => prev ? { ...prev, run_status: 'running', run_error: null } : prev)
      } else {
        setRunMsg(result.signals_rerun_required
          ? '人工筆記已儲存，請重新產生訊號套用'
          : '人工筆記已儲存')
      }
      await fetchAll().catch(() => {})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '儲存人工筆記失敗')
      if (rerunSignals) setRunning(false)
    } finally {
      setSavingNote(false)
    }
  }

  const handleUsePreviousMarketNoteDraft = () => {
    const note = summary?.manual_market_note
    if (!note) return
    const nextDate = workflowStatus?.data_as_of || todayTaipei()
    setNoteForm({
      date: nextDate,
      title: `${nextDate} 盤後風控筆記`,
      risk_level: note.risk_level || 'caution',
      headline: note.headline || '',
      source: 'manual',
      position_guidance: note.position_guidance || '',
      market_actions: note.market_actions ?? [],
      index_notes: note.index_notes ?? [],
      stock_notes: note.stock_notes ?? [],
      rules: note.rules ?? [],
    })
    setNoteActionsText((note.market_actions ?? []).join('\n'))
    setRunMsg(`已沿用 ${note.date} 筆記作為 ${nextDate} 草稿，請更新今天盤勢後再儲存`)
  }

  const handleClearMarketNoteDraft = () => {
    const nextDate = workflowStatus?.data_as_of || todayTaipei()
    setNoteForm({ ...emptyMarketNoteForm(), date: nextDate })
    setNoteActionsText('')
    setRunMsg('已清空人工盤後筆記草稿')
  }

  const handleSaveDecisionJournal = async (entry: DecisionJournalCreate) => {
    setError('')
    setRunMsg('')
    try {
      await api.createDecisionJournalEntry(entry)
      const [workflow, pm] = await Promise.all([
        api.getWorkflowStatus(),
        api.getPmWorklist(),
      ])
      setWorkflowStatus(workflow)
      setPmWorklist(pm)
      await refreshDecisionJournal(workflow, entry.date, 'all', '')
      setRunMsg('決策日誌已儲存')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '儲存決策日誌失敗')
      throw e
    }
  }

  const handleBulkCreateDecisionJournal = async (date: string) => {
    setError('')
    setRunMsg('')
    try {
      const result = await api.createDecisionJournalFromPortfolioTasks(date)
      const [workflow, pm] = await Promise.all([
        api.getWorkflowStatus(),
        api.getPmWorklist(),
      ])
      setWorkflowStatus(workflow)
      setPmWorklist(pm)
      await refreshDecisionJournal(workflow, result.date, 'all', '')
      setRunMsg(`已批次補齊 ${result.created_count} 筆決策日誌${result.skipped_count ? `，略過 ${result.skipped_count} 筆已存在紀錄` : ''}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '批次補齊決策日誌失敗')
      throw e
    }
  }

  const handleBulkCreateUniverseReviewJournal = async (date?: string | null, limit = 10) => {
    setError('')
    setRunMsg('')
    try {
      const effectiveDate = date || workflowStatus?.data_as_of || todayInputValue()
      const result = await api.createDecisionJournalFromUniverseReport(effectiveDate, limit)
      const [workflow, pm, dc] = await Promise.all([
        api.getWorkflowStatus(),
        api.getPmWorklist(),
        api.getDailyCheckOrNull(),
      ])
      setWorkflowStatus(workflow)
      setPmWorklist(pm)
      setDailyCheck(dc)
      await refreshDecisionJournal(workflow, result.date, 'all', '')
      setRunMsg(`已從候選股報表補 ${result.created_count} 筆復盤紀錄${result.skipped_count ? `，略過 ${result.skipped_count} 筆已存在紀錄` : ''}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '批次補候選股復盤失敗')
      throw e
    }
  }

  const handleDeleteDecisionJournal = async (id: string) => {
    setError('')
    setRunMsg('')
    try {
      await api.deleteDecisionJournalEntry(id)
      const [workflow, pm] = await Promise.all([
        api.getWorkflowStatus(),
        api.getPmWorklist(),
      ])
      setWorkflowStatus(workflow)
      setPmWorklist(pm)
      await refreshDecisionJournal(workflow)
      setRunMsg('決策日誌已刪除')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '刪除決策日誌失敗')
      throw e
    }
  }

  const handleUpdateDecisionJournal = async (id: string, entry: DecisionJournalCreate) => {
    setError('')
    setRunMsg('')
    try {
      await api.updateDecisionJournalEntry(id, entry)
      const [workflow, pm] = await Promise.all([
        api.getWorkflowStatus(),
        api.getPmWorklist(),
      ])
      setWorkflowStatus(workflow)
      setPmWorklist(pm)
      await refreshDecisionJournal(workflow, entry.date, 'all', '')
      setRunMsg('決策日誌已更新')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '更新決策日誌失敗')
      throw e
    }
  }

  const handleJournalDraftFromTask = (task: WorkflowPortfolioTask) => {
    const dataDate = workflowStatus?.data_as_of || todayInputValue()
    setJournalDateFilter(dataDate)
    setJournalCodeFilter(task.code)
    setDecisionDraft({
      nonce: Date.now(),
      date: dataDate,
      code: task.code,
      name: task.name,
      decision: workflowActionToDecision(task.action),
      reason: task.reason,
      shares: task.holding_shares ?? null,
      key_price: task.key_price ?? '',
      invalidation: task.invalidation ?? '',
      source: 'workflow',
    })
    setRunMsg(`已帶入 ${task.name} 的決策日誌草稿`)
  }

  const handleDecisionJournalFilterChange = async (date: string, decision: DecisionJournalDecision | 'all', code: string) => {
    setError('')
    setRunMsg('')
    try {
      await refreshDecisionJournal(workflowStatus, date, decision, code)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '篩選決策日誌失敗')
    }
  }

  const refreshFundamentalsWorkflow = async () => {
    const [fs, wf] = await Promise.all([
      api.getFundamentalsStatus(),
      api.getWorkflowStatus(),
    ])
    setFundamentalsStatus(fs)
    setWorkflowStatus(wf)
  }

  const handlePreviewFundamentalsMerge = async () => {
    setError('')
    setRunMsg('')
    setMergingFundamentals(true)
    try {
      const result = await api.mergeFundamentalsPriorityFill(true)
      setFundamentalsMergeResult(result)
      setRunMsg(`基本面合併預覽：${result.updated_code_count} 檔 / ${result.updated_field_count} 欄會更新`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '預覽基本面合併失敗')
    } finally {
      setMergingFundamentals(false)
    }
  }

  const handleApplyFundamentalsMerge = async () => {
    const ok = window.confirm('確定要把 fundamentals_priority_fill.csv 合併回 fundamentals.csv，並匯入 fundamentals.json？')
    if (!ok) return
    setError('')
    setRunMsg('')
    setMergingFundamentals(true)
    try {
      const result = await api.mergeFundamentalsPriorityFill(false, 'MERGE_PRIORITY_FUNDAMENTALS')
      setFundamentalsMergeResult(result)
      await refreshFundamentalsWorkflow()
      setRunMsg(`基本面已合併：${result.updated_code_count} 檔 / ${result.updated_field_count} 欄，JSON 匯入 ${result.imported_count ?? 0} 檔`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '合併基本面資料失敗')
    } finally {
      setMergingFundamentals(false)
    }
  }

  if (loading) return <p className="page-loading">載入中…</p>

  const fmtDate = (s?: string | null) => s ? s.slice(0, 10) : '—'
  const fmtDatetime = (s?: string | null) => s ? s.slice(0, 16).replace('T', ' ') : '—'
  const isDataRunning = dataStatus?.last_run_status === 'running'
  const isSignalsRunning = status?.run_status === 'running'
  const isSignalBusy = running || isSignalsRunning
  const isBusy = isSignalBusy || refreshing || updating || savingNote || mergingFundamentals
  const showMarketNoteForm = Boolean(status?.manual_note_status?.update_required)
  const canSaveMarketNote = Boolean(noteForm.date && noteForm.title.trim() && noteForm.headline.trim())
  const hasMarketNoteDraft = Boolean(
    noteForm.title.trim()
    || noteForm.headline.trim()
    || noteForm.position_guidance?.trim()
    || noteActionsText.trim()
  )

  return (
    <div>
      {/* ── 資料更新中 banner ── */}
      {isDataRunning && (
        <div className="alert alert-running" role="status" style={{ marginBottom: 20 }}>
          <div className="alert-title">
            <span className="spinner" aria-hidden="true" />
            資料更新中，請稍候…
          </div>
          <div className="alert-meta">開始時間：{fmtDatetime(dataStatus?.last_run_started_at)}</div>
        </div>
      )}
      {isSignalsRunning && (
        <div className="alert alert-running" role="status" style={{ marginBottom: 20 }}>
          <div className="alert-title">
            <span className="spinner" aria-hidden="true" />
            訊號計算中，完成後會自動刷新…
          </div>
        </div>
      )}

      <DecisionConsole
        dataStatus={dataStatus}
        updateWorkflow={updateWorkflow}
        worklist={pmWorklist}
        dailyBrief={dailyBrief}
        workflow={workflowStatus}
        busy={isBusy || isDataRunning}
        onFocusFundamentals={() => focusSection(fundamentalsRef)}
        onFocusDecisionJournal={() => focusSection(decisionJournalRef)}
        onFocusDailyCheck={() => focusSection(dailyCheckRef)}
        onFocusMarketNote={() => focusSection(marketNoteRef)}
        onNavigateAnalysis={onNavigateAnalysis}
      />

      {dataStatus?.outputs_lag_raw_data && !isDataRunning && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
          <div className="alert-row">
            <div>
              <div className="alert-title">原始日線已更新，交易輸出尚未重算</div>
              <div className="alert-meta">
                OHLCV 最新日：<strong>{fmtDate(dataStatus.raw_ohlcv_as_of)}</strong>
                {' '}／ 報表資料日：<strong>{fmtDate(dataStatus.last_data_as_of)}</strong>
              </div>
              {dataStatus.raw_data_warning && (
                <div className="alert-meta">{dataStatus.raw_data_warning}</div>
              )}
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleRun}
              disabled={isBusy || isSignalsRunning}
            >
              {isSignalsRunning ? '重算中…' : '重算訊號'}
            </button>
          </div>
        </div>
      )}
      {dataStatus?.last_run_status === 'failed' && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
          <div className="alert-title">
            資料更新失敗
            {dataStatus.last_error_summary && (
              <span className="alert-error-summary">：{dataStatus.last_error_summary}</span>
            )}
          </div>
          <div className="alert-meta">
            資料最新日：<strong>{fmtDate(dataStatus.last_data_as_of)}</strong>
          </div>
        </div>
      )}
      <ParseErrorAlert status={status} />

      <PmWorklistBox
        worklist={pmWorklist}
        busy={isBusy || isDataRunning}
        universeReviewWorkflow={universeReviewWorkflow}
        onFocusFundamentals={() => focusSection(fundamentalsRef)}
        onFocusDecisionJournal={() => focusSection(decisionJournalRef)}
        onFocusDailyCheck={() => focusSection(dailyCheckRef)}
        onRunUniverseReviewBatch={handleBulkCreateUniverseReviewJournal}
      />
      <UpdateWorkflowBox workflow={updateWorkflow} />
      <div ref={dailyCheckRef}>
        <DailyCheckBox
          report={dailyCheck}
          expectedDataAsOf={workflowStatus?.data_as_of || dataStatus?.last_data_as_of}
        />
      </div>
      <DataRepairQueueBox
        universe={universe}
        onNavigateAnalysis={onNavigateAnalysis}
      />
      <WorkflowStatusBox
        workflow={workflowStatus}
        busy={isBusy || isDataRunning}
        onUpdateData={handleUpdateNow}
        onRunSignals={handleRun}
        onFocusMarketNote={() => focusSection(marketNoteRef)}
        onFocusDecisionJournal={() => focusSection(decisionJournalRef)}
        onFocusFundamentals={() => focusSection(fundamentalsRef)}
        onNavigateUniverseReport={onNavigateUniverseReport}
        onNavigateAnalysis={onNavigateAnalysis}
        onJournalDraft={handleJournalDraftFromTask}
      />
      <div ref={decisionJournalRef} className="dashboard-anchor-section">
        <DecisionJournalBox
          entries={decisionJournal}
          summary={decisionJournalSummary}
          universeReviewWorkflow={universeReviewWorkflow}
          defaultDate={workflowStatus?.data_as_of}
          filterDate={journalDateFilter || workflowStatus?.data_as_of || todayInputValue()}
          filterDecision={journalDecisionFilter}
          filterCode={journalCodeFilter}
          portfolioTasks={workflowStatus?.portfolio_tasks ?? []}
          busy={isBusy || isDataRunning}
          draft={decisionDraft}
          onFilterChange={handleDecisionJournalFilterChange}
          onJournalDraft={handleJournalDraftFromTask}
          onNavigateAnalysis={onNavigateAnalysis}
          onSave={handleSaveDecisionJournal}
          onBulkCreate={handleBulkCreateDecisionJournal}
          onBulkCreateUniverseReview={handleBulkCreateUniverseReviewJournal}
          onUpdate={handleUpdateDecisionJournal}
          onDelete={handleDeleteDecisionJournal}
        />
      </div>
      <OldWangMarketBox summary={summary} />
      <ManualMarketNoteBox summary={summary} />
      <DailyBriefBox
        brief={dailyBrief}
        manualReview={manualReview}
        running={isSignalsRunning}
        onNavigateAnalysis={onNavigateAnalysis}
      />
      {showMarketNoteForm && (
        <div className="market-note-editor dashboard-anchor-section" ref={marketNoteRef}>
          <div className="market-note-editor-head">
            <div>
              <span className="old-wang-market-label">更新人工盤後筆記</span>
              <strong>貼上今天的盤後摘要</strong>
            </div>
            <div className="market-note-editor-actions">
              {summary?.manual_market_note && (
                <button
                  className="btn btn-ghost"
                  onClick={handleUsePreviousMarketNoteDraft}
                  disabled={isBusy || isDataRunning}
                >
                  沿用舊筆記
                </button>
              )}
              {hasMarketNoteDraft && (
                <button
                  className="btn btn-ghost"
                  onClick={handleClearMarketNoteDraft}
                  disabled={isBusy || isDataRunning}
                >
                  清空草稿
                </button>
              )}
              <button
                className="btn btn-ghost"
                onClick={() => handleSaveMarketNote(false)}
                disabled={isBusy || isDataRunning || !canSaveMarketNote}
              >
                {savingNote && !running ? '儲存中…' : '儲存筆記'}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleSaveMarketNote(true)}
                disabled={isBusy || isDataRunning || !canSaveMarketNote}
              >
                {savingNote && isSignalBusy ? '處理中…' : '儲存並重算'}
              </button>
            </div>
          </div>
          {summary?.manual_market_note?.is_stale && (
            <div className="market-note-draft-hint">
              可先沿用 {summary.manual_market_note.date} 筆記作為草稿，再改成今天的大盤、櫃買與強弱族群。
            </div>
          )}

          <div className="market-note-editor-grid">
            <div className="form-group">
              <label>日期</label>
              <input
                type="date"
                value={noteForm.date}
                onChange={e => setNoteForm(prev => ({ ...prev, date: e.target.value }))}
              />
              <small className="market-note-date-hint">
                預設使用訊號資料日 {workflowStatus?.data_as_of || '—'}
              </small>
            </div>
            <div className="form-group">
              <label>風險等級</label>
              <select
                value={noteForm.risk_level}
                onChange={e => setNoteForm(prev => ({ ...prev, risk_level: e.target.value }))}
              >
                <option value="risk">風險</option>
                <option value="caution">觀察</option>
                <option value="neutral">中性</option>
                <option value="strong">偏多</option>
              </select>
            </div>
            <div className="form-group market-note-wide">
              <label>標題</label>
              <input
                value={noteForm.title}
                onChange={e => setNoteForm(prev => ({ ...prev, title: e.target.value }))}
                placeholder="例如：5/21 盤後風控筆記"
              />
            </div>
            <div className="form-group market-note-wide">
              <label>摘要</label>
              <textarea
                rows={3}
                value={noteForm.headline}
                onChange={e => setNoteForm(prev => ({ ...prev, headline: e.target.value }))}
                placeholder="貼上今天大盤、櫃買、美股與操作水位的重點摘要"
              />
            </div>
            <div className="form-group market-note-wide">
              <label>水位 / 操作語氣</label>
              <textarea
                rows={2}
                value={noteForm.position_guidance ?? ''}
                onChange={e => setNoteForm(prev => ({ ...prev, position_guidance: e.target.value }))}
                placeholder="例如：短線水位維持五成，弱勢股優先處理，強勢股守 MA10 續抱"
              />
            </div>
            <div className="form-group market-note-wide">
              <label>明日檢查事項</label>
              <textarea
                rows={4}
                value={noteActionsText}
                onChange={e => setNoteActionsText(e.target.value)}
                placeholder="一行一項，例如：&#10;確認 TSE/OTC 是否守 MA10&#10;檢查記憶體強勢股是否跌破爆大量低點"
              />
            </div>
          </div>
        </div>
      )}
      <div ref={fundamentalsRef} className="dashboard-anchor-section">
        <StrategyGuideBox
          status={status}
          fundamentalsStatus={fundamentalsStatus}
          mergeResult={fundamentalsMergeResult}
          merging={mergingFundamentals}
          signalsBusy={isSignalBusy}
          onPreviewMerge={handlePreviewFundamentalsMerge}
          onApplyMerge={handleApplyFundamentalsMerge}
          onRunSignals={handleRun}
        />
      </div>

      {/* ── Actions ── */}
      <div className="dash-actions">
        <button
          className="btn btn-secondary"
          onClick={handleUpdateNow}
          disabled={isBusy || updating || isDataRunning}
          title="觸發後端 backfill + signals 全流程更新"
        >
          {(updating || isDataRunning)
            ? <><span className="spinner spinner-sm" aria-hidden="true" />更新中…</>
            : '立即更新資料'}
        </button>

        <button className="btn btn-primary" onClick={handleRun} disabled={isBusy || isDataRunning}>
          {isSignalBusy ? '產生中…' : '重新產生訊號'}
        </button>

        {/* 若資料不舊，顯示獨立刷新按鈕（stale 時已整合在 banner 中） */}
        {!dataStatus?.is_stale && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleRefresh}
            disabled={isBusy || isDataRunning}
            title="重新載入狀態"
          >
            {refreshing ? <><span className="spinner spinner-sm" aria-hidden="true" />更新中…</> : '⟳ 重新整理'}
          </button>
        )}

        <a
          className="btn btn-ghost"
          href="/api/stocks/signals/universe_report"
          download="universe_report.csv"
        >
          ⬇ 下載 universe_report.csv
        </a>

        {runMsg && <span className="run-msg">{runMsg}</span>}
        {error && <span className="form-error">{error}</span>}
      </div>

      {/* ── Status ── */}
      {status && (
        <>
          <div className="dash-section">
            <h3 className="dash-section-title">輸出檔案</h3>
            <div className="stock-card" style={{ padding: '10px 16px' }}>
              <table className="status-table">
                <tbody>
                  <StatusRow label="summary.json" info={status.out_files.summary_json} />
                  <StatusRow label="universe_report.csv" info={status.out_files.universe_report_csv} />
                  <StatusRow
                    label="daily_brief.json"
                    info={status.out_files.daily_brief_json}
                    extra={status.out_files.daily_brief_json.update_required ? '需更新' : undefined}
                  />
                </tbody>
              </table>
            </div>
          </div>

          <div className="dash-section">
            <h3 className="dash-section-title">資料來源</h3>
            <div className="stock-card" style={{ padding: '10px 16px' }}>
              <table className="status-table">
                <tbody>
                  <StatusRow label="leaders.json" info={status.data_files.leaders_json} />
                  <StatusRow label="ohlcv.csv" info={status.data_files.ohlcv_csv} />
                  {status.data_files.market_notes_json && (
                    <StatusRow
                      label="market_notes.json"
                      info={status.data_files.market_notes_json}
                      optional
                      extra={status.manual_note_status?.update_required
                        ? `需更新 · 舊筆記 ${status.manual_note_status.stale_trading_days ?? 0} 個交易日`
                        : status.manual_note_status?.status_label}
                    />
                  )}
                  {status.data_files.fundamentals_json && (
                    <StatusRow label="fundamentals.json" info={status.data_files.fundamentals_json} optional />
                  )}
                  <StatusRow label="positions.json" info={status.data_files.positions_json} optional />
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <ChangeReport summary={summary} />

      {/* ── Recommendations ── */}
      <div className="dash-section">
        <div className="dash-section-heading">
          <h3 className="dash-section-title">買入推薦</h3>
          <div className="segmented-control" aria-label="推薦策略切換">
            {STRATEGY_OPTIONS.map(option => (
              <button
                key={option.key}
                type="button"
                className={strategy === option.key ? 'active' : ''}
                onClick={() => handleStrategyChange(option.key)}
                title={option.desc}
                disabled={refreshing || running || isDataRunning}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        {recs.length === 0 ? (
          summary
            ? <NoSignalExplainer summary={summary} />
            : <p className="empty-hint">尚無買入訊號，請先產生訊號。</p>
        ) : (
          <div className="stock-grid">
            {recs.map(rec => (
              <RecCard
                key={rec.stock_id}
                rec={rec}
                onAnalysis={onNavigateAnalysis}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
