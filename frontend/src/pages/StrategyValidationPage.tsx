import { Fragment, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type {
  StrategyValidationOpenPosition,
  StrategyValidationReport,
  StrategyValidationResult,
  StrategyValidationTrade,
  UsStrategyValidationReport,
} from '../types'

type Mode = 'combined' | 'old_wang' | 'steady_momentum'
type StatusFilter = 'all' | 'open' | 'closed' | 'profit' | 'loss'

interface StockLedger {
  code: string
  name: string
  market: string
  tradingviewUrl: string
  events: StrategyValidationTrade[]
  open: StrategyValidationOpenPosition | null
  realizedPnl: number
  unrealizedPnl: number
  totalPnl: number
  invested: number
  returnPct: number | null
  strategies: string[]
}

const MODE_ORDER: Mode[] = ['combined', 'old_wang', 'steady_momentum']

const fmtMoney = (value: number, sign = false) => {
  const prefix = sign && value > 0 ? '+' : ''
  return `${prefix}${Math.round(value).toLocaleString()} 元`
}

const fmtPrice = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 3 })
const fmtPct = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
const fmtDateTime = (value: string) => value.slice(0, 16).replace('T', ' ')
const fmtStrategy = (values: string[]) => values
  .join(' + ')
  .replace(/old_wang/g, '老王')
  .replace(/steady_momentum/g, '穩健動能')
const fmtRiskLevel = (value: string) => ({
  normal: '未加防守',
  watch: '警戒',
  defensive: '防守',
  extreme: '極端',
  unknown: '資料不足',
}[value] ?? value)

function UsStrategyValidationPanel() {
  const [startDate, setStartDate] = useState('2025-07-01')
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10))
  const [report, setReport] = useState<UsStrategyValidationReport | null>(null)
  const [strategy, setStrategy] = useState('us_trend_follow')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    if (!startDate || !endDate || startDate > endDate || running) return
    setRunning(true); setError('')
    try {
      const value = await api.runUsStrategyValidation(startDate, endDate)
      setReport(value)
      setStartDate(value.start_date); setEndDate(value.end_date)
    } catch (err) {
      setError(err instanceof Error ? err.message : '美股策略驗收失敗')
    } finally { setRunning(false) }
  }

  const result = report?.results[strategy]
  const summary = result?.summary ?? {}
  const completed = Number(summary.completed_trades ?? summary.n ?? 0)
  const signals = Number(summary.signals ?? 0)
  const unresolved = Number(summary.unresolved_trades ?? 0)
  const winRate = summary.win_rate_pct == null ? null : Number(summary.win_rate_pct)
  const avgReturn = summary.avg_return_pct == null ? (summary.avg_pct == null ? null : Number(summary.avg_pct)) : Number(summary.avg_return_pct)

  return <div className="strategy-validation-page">
    <div className="validation-title-row"><div><h2>策略驗收 · 美股</h2><p>逐筆等權 walk-forward · D 日收盤訊號 → D+1 open · 非投組淨值</p></div></div>
    <section className="validation-range-panel" aria-label="美股回測日期區間">
      <label>開始日期<input type="date" value={startDate} max={endDate} onChange={event => setStartDate(event.target.value)} /></label><span>至</span>
      <label>結束日期<input type="date" value={endDate} min={startDate} onChange={event => setEndDate(event.target.value)} /></label>
      <button type="button" className="btn btn-primary" disabled={running || !startDate || !endDate || startDate > endDate} onClick={run}>{running ? '回放計算中…' : '執行區間測試'}</button>
      <small>使用美股自己的兩套策略，不套用台股策略。</small>
    </section>
    <p className="validation-disclaimer" role="note">
      紙上回放僅供驗證，<strong>非推薦、非買賣建議、非下單指令</strong>。
      任意調整區間容易挑出好看的結果（多重測試偏誤）；已知代價（空頭年為負、生存者偏差）見
      5 年凍結參數評估報告，單一區間數字不推翻也不證實它。
    </p>
    {error && <div className="page-error" role="alert">{error}</div>}
    {report && <>
      <div className="validation-mode-tabs" role="tablist" aria-label="美股策略">
        {Object.entries(report.results).map(([key, value]) => <button key={key} type="button" role="tab" aria-selected={strategy === key} className={strategy === key ? 'active' : ''} onClick={() => setStrategy(key)}>{value.strategy_label}</button>)}
      </div>
      {result && <>
        <section className="validation-summary-band us-validation-summary" aria-label="美股策略結果">
          <div><span>訊號筆數</span><strong>{signals}</strong></div><div><span>已完成</span><strong>{completed}</strong></div>
          <div><span>未完成</span><strong>{unresolved}</strong></div><div><span>勝率</span><strong>{winRate == null ? '—' : `${winRate.toFixed(1)}%`}</strong></div>
          <div><span>平均報酬</span><strong className={(avgReturn ?? 0) >= 0 ? 'pnl-positive' : 'pnl-negative'}>{avgReturn == null ? '—' : fmtPct(avgReturn)}</strong></div>
          <div><span>實際資料區間</span><strong>{report.start_date}～{report.end_date}</strong></div>
        </section>
        <div className="validation-method-strip"><span>{report.method}</span><b>·</b><span>退出規則：{result.exit_rule}</span></div>
        <div className="validation-table-wrap"><table className="validation-table us-validation-table"><thead><tr><th>股票</th><th>訊號日</th><th>進場</th><th>出場</th><th>持有</th><th>報酬</th><th>核對</th></tr></thead><tbody>
          {result.trades.map((trade, index) => <tr key={`${trade.code}-${trade.signal_date}-${index}`}><td><strong>{trade.name}</strong><small>{trade.code} · {trade.category}</small></td><td>{trade.signal_date}</td><td>{trade.entry_date ? <><strong>{trade.entry_date}</strong><small>USD {trade.entry_price?.toFixed(2)}</small></> : '未成交'}</td><td>{trade.exit_date ? <><strong>{trade.exit_date}</strong><small>USD {trade.exit_price?.toFixed(2)} · {trade.exit_reason}</small></> : <span className="validation-status open">持有／未解析</span>}</td><td>{trade.holding_trading_days == null ? '—' : `${trade.holding_trading_days} 日`}</td><td><strong className={(trade.return_pct ?? 0) >= 0 ? 'pnl-positive' : 'pnl-negative'}>{trade.return_pct == null ? '—' : fmtPct(trade.return_pct)}</strong></td><td><a href={trade.tradingview_url} target="_blank" rel="noreferrer">TradingView</a></td></tr>)}
        </tbody></table>{result.trades.length === 0 && <div className="validation-empty">此區間沒有策略交易訊號</div>}</div>
      </>}
    </>}
    {!report && !error && <div className="validation-empty">選擇日期後執行，即可比較美股兩套策略。</div>}
  </div>
}

function buildLedgers(result: StrategyValidationResult): StockLedger[] {
  const tradesByCode = new Map<string, StrategyValidationTrade[]>()
  result.trades.forEach(trade => {
    const current = tradesByCode.get(trade.code) ?? []
    current.push(trade)
    tradesByCode.set(trade.code, current)
  })
  const openByCode = new Map(result.open_positions.map(position => [position.code, position]))
  const codes = new Set([...tradesByCode.keys(), ...openByCode.keys()])

  return [...codes].map(code => {
    const events = (tradesByCode.get(code) ?? []).sort((a, b) => a.fill_date.localeCompare(b.fill_date))
    const open = openByCode.get(code) ?? null
    const reference = events[0] ?? open
    const realizedPnl = events.reduce((sum, event) => sum + (event.realized_pnl ?? 0), 0)
    const unrealizedPnl = open?.unrealized_pnl_after_exit_cost ?? 0
    const totalPnl = realizedPnl + unrealizedPnl
    const invested = events
      .filter(event => event.side === 'buy')
      .reduce((sum, event) => sum + event.fill_price * event.shares + event.fee, 0)
    return {
      code,
      name: reference?.name ?? code,
      market: reference?.market ?? 'TWSE',
      tradingviewUrl: reference?.tradingview_url ?? '',
      events,
      open,
      realizedPnl,
      unrealizedPnl,
      totalPnl,
      invested,
      returnPct: invested > 0 ? totalPnl / invested * 100 : null,
      // 後端的 strategy 是複合字串（old_wang+steady_momentum），直接去重只比整串，
      // 同一檔先後符合「只有老王」與「兩套都符合」時會印成「老王 + 老王+穩健動能」
      strategies: [...new Set(
        events.map(event => event.strategy)
          .concat(open?.strategy ?? [])
          .filter(Boolean)
          .flatMap(tag => tag.split('+'))
      )],
    }
  }).sort((a, b) => b.totalPnl - a.totalPnl)
}

function TaiwanStrategyValidationPanel({ onNavigateAnalysis }: { onNavigateAnalysis: (code: string) => void }) {
  const [report, setReport] = useState<StrategyValidationReport | null>(null)
  const [mode, setMode] = useState<Mode>('combined')
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [keyword, setKeyword] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    api.getStrategyValidation().then(value => {
      setReport(value)
      const initial = value.results.combined ?? Object.values(value.results)[0]
      setStartDate(initial?.start_date ?? '')
      setEndDate(initial?.end_date ?? '')
    }).catch(err => setError(err instanceof Error ? err.message : '策略驗收報告讀取失敗'))
  }, [])

  const runRange = async () => {
    if (!startDate || !endDate || running) return
    setRunning(true)
    setError('')
    try {
      await api.runStrategyValidation(startDate, endDate)
      // 背景執行：輪詢狀態直到 success / failed（全窗口回放可能需要數分鐘）
      for (;;) {
        await new Promise(resolve => setTimeout(resolve, 4000))
        const status = await api.getStrategyValidationStatus()
        if (status.status === 'failed') throw new Error(status.error ?? '區間測試失敗')
        if (status.status === 'success') break
      }
      const value = await api.getStrategyValidation()
      setReport(value)
      setExpanded(null)
      const actual = value.results[mode] ?? value.results.combined
      if (actual) {
        setStartDate(actual.start_date)
        setEndDate(actual.end_date)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '區間測試失敗')
    } finally {
      setRunning(false)
    }
  }

  const result = report?.results[mode]
  const ledgers = useMemo(() => result ? buildLedgers(result) : [], [result])
  const visible = useMemo(() => {
    const query = keyword.trim().toLowerCase()
    return ledgers.filter(item => {
      if (query && !`${item.code} ${item.name}`.toLowerCase().includes(query)) return false
      if (filter === 'open' && !item.open) return false
      if (filter === 'closed' && item.open) return false
      if (filter === 'profit' && item.totalPnl <= 0) return false
      if (filter === 'loss' && item.totalPnl >= 0) return false
      return true
    })
  }, [filter, keyword, ledgers])

  if (error && !report) return <div className="page-error">{error}</div>
  if (!report || !result) return <div className="page-loading">載入策略驗收報告...</div>

  const topContributor = ledgers[0]
  const concentration = topContributor && result.net_pnl > 0 ? topContributor.totalPnl / result.net_pnl * 100 : 0
  const estimatedFinalCosts = result.total_fees + result.total_tax + result.open_positions.reduce(
    (sum, position) => sum + (position.close * position.shares - position.estimated_liquidation_value),
    0,
  )

  return (
    <div className="strategy-validation-page">
      <div className="validation-title-row">
        <div>
          <h2>策略驗收</h2>
          <p>{result.start_date} 至 {result.end_date} · 期初空手 · 紙上回放</p>
        </div>
        <span className="validation-generated">產生於 {fmtDateTime(report.generated_at)}</span>
      </div>

      <div className="validation-mode-tabs" role="tablist" aria-label="策略帳戶">
        {MODE_ORDER.filter(key => report.results[key]).map(key => (
          <button key={key} type="button" role="tab" aria-selected={mode === key} className={mode === key ? 'active' : ''} onClick={() => setMode(key)}>
            {report.results[key].mode_label}
          </button>
        ))}
      </div>

      <section className="validation-range-panel" aria-label="回測日期區間">
        <label>開始日期<input type="date" value={startDate} max={endDate || undefined} onChange={event => setStartDate(event.target.value)} /></label>
        <span>至</span>
        <label>結束日期<input type="date" value={endDate} min={startDate || undefined} onChange={event => setEndDate(event.target.value)} /></label>
        <button type="button" className="btn btn-primary" disabled={running || !startDate || !endDate || startDate > endDate} onClick={runRange}>{running ? '背景回放中…' : '執行區間測試'}</button>
        <small>以 100 萬元空手重新回放完整區間；在背景執行，離開頁面不會中斷，回來重新整理即可看到結果。</small>
      </section>
      <p className="validation-disclaimer" role="note">
        紙上回放僅供驗證，<strong>非推薦、非買賣建議、非下單指令</strong>。
        任意調整區間容易挑出好看的結果（多重測試偏誤）；單一區間的漂亮數字不是策略有效的證據，
        正式結論以凍結參數的長期評估報告為準（docs/ai/strategy-evaluation-ledger.md）。
      </p>
      {error && <div className="page-error" role="alert">{error}</div>}

      <section className="validation-summary-band" aria-label="投組結果">
        <div><span>期末淨值</span><strong>{fmtMoney(result.final_equity_after_estimated_liquidation_cost)}</strong></div>
        <div><span>淨損益</span><strong className={result.net_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>{fmtMoney(result.net_pnl, true)}</strong></div>
        <div><span>報酬率</span><strong className={result.return_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}>{fmtPct(result.return_pct)}</strong></div>
        <div><span>最大回撤</span><strong className="pnl-negative">-{result.max_drawdown_pct.toFixed(2)}%</strong></div>
        <div><span>估計總成本</span><strong>{fmtMoney(estimatedFinalCosts)}</strong></div>
        <div><span>交易 / 持股</span><strong>{result.buy_count} 買 · {result.sell_count} 賣 · {result.planned_stop_count ?? 0} 停損 · {result.open_positions.length} 持有</strong></div>
      </section>

      <div className="validation-method-strip">
        <span>D 日收盤訊號</span><b>→</b><span>D+1 開盤成交</span><b>→</b><span>計畫停損／日線退出</span><b>→</b><span>期末扣費稅清算</span>
      </div>

      {result.entry_guardrails && (
        <div className="validation-risk-banner validation-guardrail-banner">
          <strong>組合風控已啟用</strong>
          <span>
            正常：單檔 {result.entry_guardrails.normal.max_position_pct}%／總曝險 {result.entry_guardrails.normal.max_exposure_pct}%／每日最多 {result.entry_guardrails.normal.max_new_positions} 個新倉；
            警戒降至 {result.entry_guardrails.watch.max_position_pct}%／{result.entry_guardrails.watch.max_exposure_pct}%／{result.entry_guardrails.watch.max_new_positions} 檔；防守、極端或盤前資料未知時停止新倉；防守後首個正常日先沿用警戒容量確認恢復。
          </span>
        </div>
      )}
      {(result.skipped_entry_count ?? 0) > 0 && (
        <details className="validation-skipped-entries">
          <summary>風控略過 {result.skipped_entry_count} 個進場候選</summary>
          <div>
            {(result.skipped_entries ?? []).map((item, index) => (
              <p key={`${item.fill_date}-${item.code}-${index}`}>
                <strong>{item.fill_date} · {item.name}（{item.code}）</strong>
                <span>{item.reason}</span>
              </p>
            ))}
          </div>
        </details>
      )}
      {(result.stop_reentry_count ?? 0) > 0 && (
        <details className="validation-skipped-entries validation-stop-reentries">
          <summary>停損後再次進場 {result.stop_reentry_count} 次</summary>
          <div>
            {(result.stop_reentries ?? []).map(item => (
              <p key={`${item.stop_date}-${item.reentry_date}-${item.code}`}>
                <strong>{item.name}（{item.code}）· 相隔 {item.sessions_until_reentry} 個交易日</strong>
                <span>{item.stop_date} {fmtRiskLevel(item.stop_risk_level)} → {item.reentry_date} {fmtRiskLevel(item.reentry_risk_level)}</span>
              </p>
            ))}
          </div>
        </details>
      )}

      {concentration >= 40 && (
        <div className="validation-risk-banner">
          <strong>集中度偏高</strong>
          <span>{topContributor.name}（{topContributor.code}）貢獻 {fmtMoney(topContributor.totalPnl, true)}，占總獲利約 {concentration.toFixed(1)}%。</span>
        </div>
      )}

      <div className="validation-toolbar">
        <div className="validation-filter-tabs" role="group" aria-label="持倉與損益篩選">
          {([['all', '全部'], ['open', '持有中'], ['closed', '已平倉'], ['profit', '獲利'], ['loss', '虧損']] as [StatusFilter, string][]).map(([key, label]) => (
            <button key={key} type="button" className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>{label}</button>
          ))}
        </div>
        <input aria-label="搜尋股票" value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="代號或名稱" />
      </div>

      <div className="validation-table-wrap">
        <table className="validation-table">
          <thead>
            <tr>
              <th>股票</th><th>策略</th><th>首次進場</th><th>最後事件</th><th>狀態</th><th>累計損益</th><th>核對</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(item => {
              const firstBuy = item.events.find(event => event.side === 'buy')
              const lastEvent = item.events[item.events.length - 1]
              const isExpanded = expanded === item.code
              return (
                <Fragment key={item.code}>
                  <tr className={isExpanded ? 'expanded' : ''}>
                    <td>
                      <button type="button" className="validation-stock-btn" onClick={() => setExpanded(isExpanded ? null : item.code)} aria-expanded={isExpanded}>
                        <strong>{item.name}</strong><span>{item.code} · {item.market}</span>
                      </button>
                    </td>
                    <td><span className="validation-strategy-tag">{fmtStrategy(item.strategies)}</span></td>
                    <td>{firstBuy ? <><strong>{firstBuy.fill_date}</strong><small>{fmtPrice(firstBuy.fill_price)} × {firstBuy.shares.toLocaleString()}</small></> : '—'}</td>
                    <td>{lastEvent ? <><strong>{lastEvent.fill_date}</strong><small>{lastEvent.side === 'buy' ? '買進' : '賣出'} {fmtPrice(lastEvent.fill_price)}</small></> : '—'}</td>
                    <td>{item.open ? <span className="validation-status open">持有 {item.open.shares.toLocaleString()}</span> : <span className="validation-status closed">已平倉</span>}</td>
                    <td><strong className={item.totalPnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>{fmtMoney(item.totalPnl, true)}</strong><small>{item.returnPct == null ? '—' : fmtPct(item.returnPct)}</small></td>
                    <td>
                      <div className="validation-link-actions">
                        <button type="button" onClick={() => onNavigateAnalysis(item.code)}>本機線圖</button>
                        <a href={item.tradingviewUrl} target="_blank" rel="noreferrer">TradingView</a>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="validation-detail-row">
                      <td colSpan={7}>
                        <div className="validation-timeline">
                          {item.events.map((event, index) => (
                            <div key={`${event.fill_date}-${event.side}-${index}`} className={`validation-event ${event.side}`}>
                              <span>{event.side === 'buy' ? '買' : '賣'}</span>
                              <div><strong>訊號 {event.signal_date} → 成交 {event.fill_date}</strong><small>{fmtPrice(event.fill_price)} 元 × {event.shares.toLocaleString()} 股 · 費 {fmtMoney(event.fee)}{event.tax ? ` · 稅 ${fmtMoney(event.tax)}` : ''}</small></div>
                              <p>{event.reason || '未記錄原因'}</p>
                              {event.realized_pnl != null && <b className={event.realized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>{fmtMoney(event.realized_pnl, true)}</b>}
                            </div>
                          ))}
                          {item.open && <div className="validation-open-mark"><strong>期末仍持有</strong><span>收盤 {fmtPrice(item.open.close)} · 預估清算損益 <b className={item.unrealizedPnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>{fmtMoney(item.unrealizedPnl, true)}</b></span></div>}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
        {visible.length === 0 && <div className="validation-empty">沒有符合條件的股票</div>}
      </div>
    </div>
  )
}

export default function StrategyValidationPage({ onNavigateAnalysis, initialRegion = 'TW' }: { onNavigateAnalysis: (code: string) => void; initialRegion?: 'TW' | 'US' }) {
  const [region, setRegion] = useState<'TW' | 'US'>(initialRegion)
  return <>
    <div className="validation-region-tabs" role="tablist" aria-label="驗收市場">
      <button type="button" role="tab" aria-selected={region === 'TW'} className={region === 'TW' ? 'active' : ''} onClick={() => setRegion('TW')}>台股</button>
      <button type="button" role="tab" aria-selected={region === 'US'} className={region === 'US' ? 'active' : ''} onClick={() => setRegion('US')}>美股</button>
    </div>
    {region === 'TW' ? <TaiwanStrategyValidationPanel onNavigateAnalysis={onNavigateAnalysis} /> : <UsStrategyValidationPanel />}
  </>
}
