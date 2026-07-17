import { useEffect, useRef, useState } from 'react'
import { ColorType, createChart } from 'lightweight-charts'
import { api } from '../api/client'
import type { UsStockAnalysis, WatchlistGroup } from '../types'

function UsChart({ data }: { data: UsStockAnalysis }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || data.ohlcv.length === 0) return
    const chart = createChart(ref.current, { height: 430, layout: { background: { type: ColorType.Solid, color: '#fff' }, textColor: '#475569' }, timeScale: { borderColor: '#e2e8f0' } })
    const candles = chart.addCandlestickSeries({ upColor: '#dc2626', downColor: '#16a34a', wickUpColor: '#dc2626', wickDownColor: '#16a34a', borderVisible: false })
    candles.setData(data.ohlcv.map(row => ({ time: row.date, open: Number(row.open), high: Number(row.high), low: Number(row.low), close: Number(row.close) })))
    const ma = (period: number) => data.ohlcv.map((row, index) => index < period - 1 ? null : ({ time: row.date, value: data.ohlcv.slice(index - period + 1, index + 1).reduce((sum, item) => sum + Number(item.close), 0) / period })).filter(Boolean) as { time: string; value: number }[]
    chart.addLineSeries({ color: '#2563eb', lineWidth: 2 }).setData(ma(20))
    chart.addLineSeries({ color: '#7c3aed', lineWidth: 2 }).setData(ma(60))
    chart.timeScale().fitContent()
    const resize = () => ref.current && chart.applyOptions({ width: ref.current.clientWidth })
    resize(); window.addEventListener('resize', resize)
    return () => { window.removeEventListener('resize', resize); chart.remove() }
  }, [data])
  return <div ref={ref} className="us-research-chart" />
}

export default function UsResearchPage({ initialCode }: { initialCode?: string }) {
  const [code, setCode] = useState(initialCode ?? 'AAPL')
  const [data, setData] = useState<UsStockAnalysis | null>(null)
  const [groups, setGroups] = useState<WatchlistGroup[]>([])
  const [group, setGroup] = useState('')
  const [error, setError] = useState('')
  const load = async (target = code) => { setError(''); try { setData(await api.getUsStockAnalysis(target.trim().toUpperCase())); setCode(target.trim().toUpperCase()) } catch (e) { setError(e instanceof Error ? e.message : '載入失敗') } }
  useEffect(() => { load(initialCode ?? 'AAPL'); api.getWatchlists().then(setGroups).catch(() => {}) }, [initialCode]) // eslint-disable-line react-hooks/exhaustive-deps
  const add = async () => { if (!data || !group) return; await api.addToWatchlist(group, data.code, data.name, 'US'); setGroup('') }
  return <main className="app-main app-main-wide"><div className="analysis-page">
    <div className="analysis-toolbar"><input className="stock-code-input" value={code} onChange={e => setCode(e.target.value.toUpperCase())} onKeyDown={e => e.key === 'Enter' && load()} placeholder="Ticker，例如 AAPL" /><button className="btn btn-primary" onClick={() => load()}>分析</button></div>
    {error && <div className="page-error">{error}</div>}
    <p className="validation-disclaimer" role="note">描述性技術觀察（指標與狀態），<strong>非推薦、非買賣建議、非下單指令</strong>；資料源為 Yahoo Finance 非官方端點（日線、不含股息）。</p>
    {data && <div className="analysis-body"><div className="analysis-title"><span>{data.name}（{data.code}）</span><span className="analysis-date">資料日 {data.as_of} · USD · {data.row_count} 筆</span><select value={group} onChange={e => setGroup(e.target.value)}><option value="">加入觀察清單…</option>{groups.map(g => <option key={g.name}>{g.name}</option>)}</select><button className="btn btn-secondary btn-sm" disabled={!group} onClick={add}>加入</button></div>
      <section className="validation-summary-band us-research-summary"><div><span>收盤</span><strong>USD {data.close?.toFixed(2) ?? '—'}</strong></div><div><span>MA20</span><strong>{data.ma20?.toFixed(2) ?? '—'}</strong></div><div><span>MA60</span><strong>{data.ma60?.toFixed(2) ?? '—'}</strong></div><div><span>RSI14</span><strong>{data.rsi14?.toFixed(1) ?? '—'}</strong></div><div><span>20 日</span><strong>{data.change_20d_pct?.toFixed(2) ?? '—'}%</strong></div><div><span>狀態</span><strong>{data.status_label}</strong></div></section>
      <UsChart data={data} /><div className="validation-method-strip">{data.reasons.join(' · ')}</div>{data.risk_notes.length > 0 && <div className="validation-risk-banner"><strong>資料／風險</strong><span>{data.risk_notes.join('；')}</span></div>}
    </div>}
  </div></main>
}
