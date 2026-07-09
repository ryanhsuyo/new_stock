import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import AnalysisPanel from '../components/AnalysisPanel'
import BuyModal from '../components/BuyModal'
import StockChart from '../components/StockChart'
import type { BuyRequest, IntradayMonitor, StockAnalysis, StockUniverseItem, TradeRecord, WatchlistGroup } from '../types'

interface Props {
  /** 從其他頁面跳轉時帶入的股票代碼；設定後自動載入分析 */
  initialCode?: string
  /** 同一檔股票重複跳轉時，用來強制重新載入 */
  requestId?: number
  /** 頁內搜尋 / 選股成功後回報目前代碼，讓 App 同步 hash 與左 rail 高亮 */
  onCodeChange?: (code: string) => void
  /** 成功加入觀察清單後通知 App，讓左 rail 重新抓取 watchlists */
  onWatchlistChanged?: () => void
}

const DATA_STATUS_HINT: Record<string, string> = {
  ok:           '',
  insufficient: '⚠ 資料不足60筆',
  no_data:      '⚠ 尚未回補',
}

const MONITOR_LABEL: Record<IntradayMonitor['monitor_signal'], string> = {
  healthy: '盤中健康',
  caution: '盤中警戒',
  risk: '風險升高',
  data_missing: '資料不足',
}

const MONITOR_CLASS: Record<IntradayMonitor['monitor_signal'], string> = {
  healthy: 'monitor-healthy',
  caution: 'monitor-caution',
  risk: 'monitor-risk',
  data_missing: 'monitor-muted',
}

const DATA_DIAGNOSTIC_LABEL: Record<string, string> = {
  ok: '資料可用',
  not_tracked: '未列入追蹤',
  no_ohlcv_data: '尚未回補日線',
  insufficient_rows: '日線不足',
}

const BACKEND_REPAIR_COMMAND = [
  'cd /Users/ryan/Desktop/code/new_stock/backend',
  'python3 scripts/daily_update.py --months 12',
].join('\n')

export default function AnalysisPage({ initialCode, requestId, onCodeChange, onWatchlistChanged }: Props) {
  const [inputVal, setInputVal]       = useState(initialCode ?? '')
  // pickerFilter 獨立於 inputVal：下拉展開時重置為空，打字時更新
  const [pickerFilter, setPickerFilter] = useState('')
  const [data, setData]               = useState<StockAnalysis | null>(null)
  const [trades, setTrades]           = useState<TradeRecord[]>([])
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState('')
  const inputRef                      = useRef<HTMLInputElement>(null)
  const pickerRef                     = useRef<HTMLDivElement>(null)
  const dropdownRef                   = useRef<HTMLDivElement>(null)
  const [showPicker, setShowPicker]   = useState(false)
  const [hoveredIdx, setHoveredIdx]   = useState(-1)

  // 動態 universe（combobox 用）
  const [universe, setUniverse]       = useState<StockUniverseItem[]>([])

  // 觀察清單
  const [groups, setGroups]           = useState<WatchlistGroup[]>([])
  const [addGroup, setAddGroup]       = useState('')
  const [addMsg, setAddMsg]           = useState('')
  const [adding, setAdding]           = useState(false)
  const [buyOpen, setBuyOpen]         = useState(false)
  const [buyMsg, setBuyMsg]           = useState('')
  const [repairMsg, setRepairMsg]     = useState('')
  const [copyMsg, setCopyMsg]         = useState('')
  const [trackingLoading, setTrackingLoading] = useState(false)
  const [intraday, setIntraday]       = useState<IntradayMonitor | null>(null)
  const [intradayLoading, setIntradayLoading] = useState(false)
  const [intradayError, setIntradayError] = useState('')
  const [intradayForm, setIntradayForm] = useState({
    price: '',
    open: '',
    high: '',
    low: '',
    volume: '',
  })

  // 初始載入 universe + watchlist groups
  useEffect(() => {
    api.getUniverse().then(setUniverse).catch(() => {})
    api.getWatchlists().then(setGroups).catch(() => {})
    api.getTrades().then(setTrades).catch(() => {})
  }, [])

  // 點選外部時收起下拉
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowPicker(false)
        setHoveredIdx(-1)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  // 若有 initialCode（從投組頁 / 左 rail 跳轉），自動設定代碼並載入
  // 已顯示同一檔時略過：避免頁內搜尋回報代碼、App 更新 initialCode 後又重覆載入
  useEffect(() => {
    if (!initialCode) return
    if (data?.code?.toUpperCase() === initialCode.toUpperCase()) return
    loadAnalysis(initialCode)
  }, [initialCode, requestId]) // eslint-disable-line react-hooks/exhaustive-deps

  // 以 pickerFilter 過濾（空白時顯示前 40；有輸入時依代碼前綴或名稱過濾）
  const filteredUniverse = useMemo(() => {
    const q = pickerFilter.trim()
    if (!q) return universe.slice(0, 40)
    const qUp = q.toUpperCase()
    return universe
      .filter(s => s.code.startsWith(qUp) || s.name.includes(q))
      .slice(0, 20)
  }, [universe, pickerFilter])

  // hoveredIdx 越界保護
  useEffect(() => {
    if (hoveredIdx >= filteredUniverse.length) setHoveredIdx(filteredUniverse.length - 1)
  }, [filteredUniverse, hoveredIdx])

  // 鍵盤選中時自動捲動到可視範圍
  useEffect(() => {
    if (!dropdownRef.current || hoveredIdx < 0) return
    const el = dropdownRef.current.children[hoveredIdx] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }, [hoveredIdx])

  async function loadAnalysis(codeOverride?: string) {
    const target = (codeOverride ?? inputVal).trim().toUpperCase()
    if (!target) {
      setError('請輸入股票代號')
      inputRef.current?.focus()
      return
    }
    setLoading(true)
    setError('')
    setAddMsg('')
    setBuyMsg('')
    setRepairMsg('')
    setCopyMsg('')
    setAddGroup('')
    setIntraday(null)
    setIntradayError('')
    try {
      const result = await api.getStockAnalysis(target)
      setData(result)
      setInputVal(target)
      // 回報目前代碼給 App：同步 hash 與左 rail 高亮（App 不會 bump requestId，故不重載本頁）
      onCodeChange?.(target)
      setIntradayForm({
        price: result.close != null ? String(result.close) : '',
        open: '',
        high: '',
        low: '',
        volume: '',
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : '載入失敗')
    } finally {
      setLoading(false)
    }
  }

  async function handleAddToWatchlist() {
    if (!addGroup || !data) return
    setAdding(true)
    setAddMsg('')
    try {
      await api.addToWatchlist(addGroup, data.code, data.name)
      setAddMsg(`已加入「${addGroup}」`)
      setAddGroup('')
      onWatchlistChanged?.()
    } catch (e) {
      setAddMsg(e instanceof Error ? e.message : '加入失敗')
    } finally {
      setAdding(false)
    }
  }

  async function handleBuySubmit(req: BuyRequest) {
    await api.buyStock(req)
    setBuyMsg(`已記錄 ${req.name}（${req.stock_id}）買入 ${req.shares.toLocaleString()} 股，價格 ${req.price}`)
    api.getTrades().then(setTrades).catch(() => {})
  }

  async function handleAddTracking() {
    if (!data) return
    setTrackingLoading(true)
    setRepairMsg('')
    try {
      const result = await api.addStockToTracking(data.code, data.name)
      await api.getUniverse().then(setUniverse).catch(() => {})
      await loadAnalysis(data.code)
      setRepairMsg(`${result.message}；下一步請複製修復指令，完成回補與訊號重算。`)
    } catch (e) {
      setRepairMsg(e instanceof Error ? e.message : '加入追蹤清單失敗')
    } finally {
      setTrackingLoading(false)
    }
  }

  async function copyRepairCommand(command?: string) {
    const repairCommand = command || data?.data_diagnostic.next_action_copy_command || BACKEND_REPAIR_COMMAND
    setCopyMsg('')
    try {
      await navigator.clipboard.writeText(repairCommand)
      setCopyMsg('已複製修復指令')
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = repairCommand
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopyMsg('已複製修復指令')
    }
  }

  function parseOptionalNumber(value: string): number | undefined {
    const trimmed = value.trim()
    if (!trimmed) return undefined
    const parsed = Number(trimmed.replace(/,/g, ''))
    return Number.isFinite(parsed) ? parsed : undefined
  }

  async function handleIntradayCheck() {
    if (!data) return
    setIntradayLoading(true)
    setIntradayError('')
    try {
      const result = await api.getIntradayMonitor(data.code, {
        price: parseOptionalNumber(intradayForm.price),
        open_price: parseOptionalNumber(intradayForm.open),
        high: parseOptionalNumber(intradayForm.high),
        low: parseOptionalNumber(intradayForm.low),
        volume: parseOptionalNumber(intradayForm.volume),
      })
      setIntraday(result)
    } catch (e) {
      setIntradayError(e instanceof Error ? e.message : '盤中監控失敗')
    } finally {
      setIntradayLoading(false)
    }
  }

  function openPicker() {
    setPickerFilter('')   // 展開時清空過濾，顯示全部候選
    setHoveredIdx(-1)
    setShowPicker(true)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!showPicker) {
      if (e.key === 'ArrowDown') { openPicker(); return }
      if (e.key === 'Enter') { loadAnalysis(); return }
      return
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHoveredIdx(i => Math.min(i + 1, filteredUniverse.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHoveredIdx(i => Math.max(i - 1, -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (hoveredIdx >= 0 && filteredUniverse[hoveredIdx]) {
        handlePickerSelect(filteredUniverse[hoveredIdx].code)
      } else {
        setShowPicker(false)
        loadAnalysis()
      }
    } else if (e.key === 'Escape') {
      setShowPicker(false)
      setHoveredIdx(-1)
    }
  }

  function handlePickerSelect(code: string) {
    setInputVal(code)
    setPickerFilter('')
    setShowPicker(false)
    setHoveredIdx(-1)
    setData(null)
    setError('')
    loadAnalysis(code)
  }

  const needsDataRepair = data ? data.data_diagnostic.status !== 'ok' : false
  const isTrackedForRepair = data ? data.data_diagnostic.status !== 'not_tracked' : false

  return (
    <div className="analysis-page">
      <div className="analysis-toolbar">
        <div className="analysis-input-wrap" ref={pickerRef}>
          <input
            ref={inputRef}
            type="text"
            className="stock-code-input"
            value={showPicker ? pickerFilter : inputVal}
            onChange={e => {
              const v = e.target.value
              setPickerFilter(v)
              setInputVal(v)
              setHoveredIdx(-1)
              setData(null)
              setError('')
              setShowPicker(true)
            }}
            onFocus={openPicker}
            onClick={openPicker}
            onKeyDown={handleKeyDown}
            placeholder="代號或名稱，例：2330 / 台積電"
            autoComplete="off"
            spellCheck={false}
          />
          {showPicker && filteredUniverse.length > 0 && (
            <div className="stock-picker-dropdown" ref={dropdownRef}>
              {filteredUniverse.map((s, idx) => (
                <div
                  key={s.code}
                  className={`stock-picker-option${idx === hoveredIdx ? ' stock-picker-option--active' : ''}`}
                  onMouseDown={e => { e.preventDefault(); handlePickerSelect(s.code) }}
                  onMouseEnter={() => setHoveredIdx(idx)}
                >
                  <span className={`picker-status-dot picker-status-${
                    s.data_status === 'ok' ? 'ok'
                    : s.data_status === 'insufficient' ? 'warn'
                    : 'none'
                  }`} />
                  <span className="picker-code">{s.code}</span>
                  <span className="picker-name">{s.name}</span>
                  {s.data_status !== 'ok' && (
                    <span className="picker-hint">{DATA_STATUS_HINT[s.data_status]}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { setShowPicker(false); loadAnalysis() }}
          disabled={loading}
        >
          {loading ? '載入中…' : '分析'}
        </button>
      </div>

      {error && <div className="page-error">{error}</div>}

      {data && (
        <div className="analysis-body">
          <h2 className="analysis-title">
            <span>{data.name}（{data.code}）</span>
            <span className="analysis-date">
              資料日：{data.data_diagnostic.last_data_as_of ?? data.as_of}
              {' · '}
              日線 {data.data_diagnostic.row_count}/{data.data_diagnostic.required_rows} 筆
            </span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setBuyOpen(true)}
              disabled={!data.data_ok || data.close === null}
              title={!data.data_ok || data.close === null ? '資料不足，無法預填買入價格' : '以最新收盤價預填，請改成真實成交價後記錄'}
            >
              記錄買入
            </button>
          </h2>
          <div className={`analysis-data-diagnostic diagnostic-${data.data_diagnostic.status}`} role="note">
            <div>
              <span className="diagnostic-badge">
                {DATA_DIAGNOSTIC_LABEL[data.data_diagnostic.status] ?? data.data_diagnostic.status}
              </span>
              <strong>價格基準：{data.data_diagnostic.price_basis_label}</strong>
              <p>{data.data_diagnostic.price_basis_note}</p>
            </div>
            <div className="diagnostic-detail">
              <span>{data.data_diagnostic.message}</span>
              {data.data_diagnostic.next_action_command && (
                <code>{data.data_diagnostic.next_action_command}</code>
              )}
              {needsDataRepair && (
                <div className="repair-steps">
                  <div className={`repair-step ${isTrackedForRepair ? 'done' : 'active'}`}>
                    <span>1</span>
                    <strong>{isTrackedForRepair ? '已列入追蹤' : '先加入追蹤清單'}</strong>
                  </div>
                  <div className={`repair-step ${isTrackedForRepair ? 'active' : ''}`}>
                    <span>2</span>
                    <strong>回補日線資料</strong>
                  </div>
                  <div className="repair-step">
                    <span>3</span>
                    <strong>重新產生訊號</strong>
                  </div>
                </div>
              )}
              {needsDataRepair && isTrackedForRepair && (
                <div className="repair-command-card">
                  <pre>{data.data_diagnostic.next_action_copy_command || BACKEND_REPAIR_COMMAND}</pre>
                  <button
                    className="btn btn-primary btn-sm diagnostic-action"
                    onClick={() => copyRepairCommand(data.data_diagnostic.next_action_copy_command)}
                    type="button"
                  >
                    複製修復指令
                  </button>
                  {copyMsg && <span className="repair-copy-msg">{copyMsg}</span>}
                </div>
              )}
              {data.data_diagnostic.status === 'not_tracked' && (
                <button
                  className="btn btn-primary btn-sm diagnostic-action"
                  onClick={handleAddTracking}
                  disabled={trackingLoading}
                >
                  {trackingLoading ? '加入中…' : '加入追蹤清單'}
                </button>
              )}
            </div>
          </div>
          {repairMsg && <div className="run-msg analysis-repair-msg">{repairMsg}</div>}
          {buyMsg && <div className="run-msg analysis-buy-msg">{buyMsg}</div>}

          {/* 資料過舊警示 */}
          {data.is_stale && (
            <div className="alert alert-stale" role="alert" style={{ padding: '8px 14px' }}>
              <span className="alert-title" style={{ fontSize: 13 }}>
                資料已 {data.stale_days} 天未更新，技術分析結果可能不準確
              </span>
            </div>
          )}

          {/* 加入觀察清單（僅資料正常時顯示） */}
          {data.data_ok && (
            <div className="watchlist-add-bar">
              <span className="watchlist-add-label">加入觀察清單：</span>
              <select
                className="watchlist-group-select"
                value={addGroup}
                onChange={e => { setAddGroup(e.target.value); setAddMsg('') }}
              >
                <option value="">選擇群組…</option>
                {groups.map(g => (
                  <option key={g.name} value={g.name}>{g.name}</option>
                ))}
              </select>
              <button
                className="btn btn-ghost btn-sm"
                onClick={handleAddToWatchlist}
                disabled={!addGroup || adding}
              >
                {adding ? '加入中…' : '確認加入'}
              </button>
              {addMsg && (
                <span className={addMsg.includes('失敗') ? 'form-error' : 'run-msg'}>
                  {addMsg}
                </span>
              )}
              {groups.length === 0 && (
                <span className="watchlist-add-hint">（請先在「觀察清單」頁建立群組）</span>
              )}
            </div>
          )}

          <StockChart data={data} trades={trades} />

          <div className="intraday-monitor-panel">
            <div className="intraday-monitor-head">
              <div>
                <h3>盤中決策監控</h3>
                <span>不改正式日線訊號，只檢查今天盤中是否破壞計畫。</span>
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleIntradayCheck}
                disabled={intradayLoading || !data.data_ok}
              >
                {intradayLoading ? '檢查中…' : '檢查盤中狀態'}
              </button>
            </div>
            <div className="intraday-input-grid">
              <label>
                目前價
                <input
                  value={intradayForm.price}
                  onChange={e => setIntradayForm(f => ({ ...f, price: e.target.value }))}
                  placeholder="例：3630"
                />
              </label>
              <label>
                開盤
                <input
                  value={intradayForm.open}
                  onChange={e => setIntradayForm(f => ({ ...f, open: e.target.value }))}
                  placeholder="選填"
                />
              </label>
              <label>
                最高
                <input
                  value={intradayForm.high}
                  onChange={e => setIntradayForm(f => ({ ...f, high: e.target.value }))}
                  placeholder="選填"
                />
              </label>
              <label>
                最低
                <input
                  value={intradayForm.low}
                  onChange={e => setIntradayForm(f => ({ ...f, low: e.target.value }))}
                  placeholder="選填"
                />
              </label>
              <label>
                成交量
                <input
                  value={intradayForm.volume}
                  onChange={e => setIntradayForm(f => ({ ...f, volume: e.target.value }))}
                  placeholder="選填，股數"
                />
              </label>
            </div>
            {intradayError && <div className="page-error">{intradayError}</div>}
            {intraday && (
              <div className={`intraday-result ${MONITOR_CLASS[intraday.monitor_signal]}`}>
                <div className="intraday-result-main">
                  <span>{MONITOR_LABEL[intraday.monitor_signal]}</span>
                  <strong>{intraday.action}</strong>
                  <em>{intraday.official_signal_note}</em>
                </div>
                <div className="intraday-metrics">
                  <span>MA5 {intraday.ma5 ?? '—'}</span>
                  <span>MA10 {intraday.ma10 ?? '—'}</span>
                  <span>MA20 {intraday.ma20 ?? '—'}</span>
                  <span>MA60 {intraday.ma60 ?? '—'}</span>
                  <span>爆量低 {intraday.volume_low_price ?? '—'}</span>
                  <span>破壞計畫 {intraday.invalidates_daily_plan ? '是' : '否'}</span>
                </div>
                {intraday.broken_ma_levels.length > 0 && (
                  <div className="intraday-chip-row">
                    {intraday.broken_ma_levels.map(level => <span key={level}>跌破 {level}</span>)}
                  </div>
                )}
                {intraday.warnings.length > 0 && (
                  <ul className="intraday-list intraday-warnings">
                    {intraday.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
                  </ul>
                )}
                {intraday.notes.length > 0 && (
                  <ul className="intraday-list">
                    {intraday.notes.map((n, idx) => <li key={idx}>{n}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>

          <AnalysisPanel data={data} />

          {buyOpen && data.close !== null && (
            <BuyModal
              stock={{ stock_id: data.code, name: data.name, price: data.close }}
              defaultDate={data.as_of}
              defaultNote={`技術分析頁記錄，預填價格為最新收盤價，請以真實成交價為準；訊號：${data.signal}，評分：${data.score}`}
              onClose={() => setBuyOpen(false)}
              onSubmit={handleBuySubmit}
            />
          )}
        </div>
      )}

      {!data && !loading && !error && (
        <p className="empty-hint">點擊輸入框展開股票清單，或輸入代號後按 Enter / 點「分析」</p>
      )}
    </div>
  )
}
