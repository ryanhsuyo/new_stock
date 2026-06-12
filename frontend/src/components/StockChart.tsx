import { useEffect, useMemo, useRef, useState } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type CandlestickSeriesOptions,
  type HistogramSeriesOptions,
  type LineSeriesOptions,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import type { StockAnalysis, SupportResistanceLine, TradeRecord } from '../types'

interface Props {
  data: StockAnalysis
  trades?: TradeRecord[]
}

interface ChartReadout {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  volMa5: number | null
  volMa10: number | null
}

// Project trend line slope from p2 to targetDate
function extendTrendLine(
  p1: { date: string; price: number },
  p2: { date: string; price: number },
  targetDate: string,
): number {
  const t1 = new Date(p1.date).getTime()
  const t2 = new Date(p2.date).getTime()
  const tEnd = new Date(targetDate).getTime()
  if (t2 <= t1) return p2.price
  const slope = (p2.price - p1.price) / (t2 - t1)
  return Math.round((p2.price + slope * (tEnd - t2)) * 100) / 100
}

// Compute simple MA from ohlcv close prices
function computeMA(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null
    const sum = closes.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
    return Math.round((sum / period) * 100) / 100
  })
}

function latestValue(values: (number | null)[]): number | null {
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (values[i] !== null) return values[i]
  }
  return null
}

function formatPrice(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

function formatVolume(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}億`
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}萬`
  return value.toLocaleString()
}

function findRecentVolumeLow(rows: StockAnalysis['ohlcv'], lookback = 30, volumeMultiplier = 1.5) {
  if (rows.length === 0) return null
  const volumes = rows.map(row => row.volume)
  const volMa20 = computeMA(volumes, 20)
  const start = Math.max(0, rows.length - lookback)
  const candidates = rows
    .slice(start)
    .map((row, offset) => {
      const index = start + offset
      const baseVolume = volMa20[index]
      const volumeRatio = baseVolume && baseVolume > 0 ? row.volume / baseVolume : null
      return { row, volumeRatio }
    })
    .filter(item => item.volumeRatio !== null && item.volumeRatio >= volumeMultiplier)
  const selected = candidates.length > 0
    ? candidates.reduce((best, item) => item.row.volume > best.row.volume ? item : best, candidates[0]).row
    : rows.slice(-lookback).reduce((best, row) => row.volume > best.volume ? row : best, rows.slice(-lookback)[0])
  const index = rows.findIndex(row => row.date === selected.date)
  const baseVolume = index >= 0 ? volMa20[index] : null
  const volumeRatio = baseVolume && baseVolume > 0 ? selected.volume / baseVolume : null
  return {
    date: selected.date,
    price: selected.low,
    volume: selected.volume,
    volumeRatio: volumeRatio ? Math.round(volumeRatio * 100) / 100 : null,
    isExplosion: candidates.length > 0,
  }
}

function buildReadout(
  rows: StockAnalysis['ohlcv'],
  date: string,
  ma5: (number | null)[],
  ma10: (number | null)[],
  ma20: (number | null)[],
  ma60: (number | null)[],
  volMa5: (number | null)[],
  volMa10: (number | null)[],
): ChartReadout | null {
  const index = rows.findIndex(row => row.date === date)
  if (index < 0) return null
  const row = rows[index]
  return {
    date: row.date,
    open: row.open,
    high: row.high,
    low: row.low,
    close: row.close,
    volume: row.volume,
    ma5: ma5[index],
    ma10: ma10[index],
    ma20: ma20[index],
    ma60: ma60[index],
    volMa5: volMa5[index],
    volMa10: volMa10[index],
  }
}

// ── 右側標籤邏輯 ────────────────────────────────────────────────────────────

// 後端 label → 短碼對照表（含空格變體）
const SHORT_LABEL: Record<string, string> = {
  '近20日低點支撐':  'S20',
  '近60日低點支撐':  'S60',
  'MA20 動態支撐':   'MA20',
  'MA60 動態支撐':   'MA60',
  'MA20動態支撐':    'MA20',
  'MA60動態支撐':    'MA60',
  '近20日高點壓力':  'R20',
  '近60日高點壓力':  'R60',
  'MA20 動態壓力':   'MA20',
  'MA60 動態壓力':   'MA60',
  'MA20動態壓力':    'MA20',
  'MA60動態壓力':    'MA60',
}

/**
 * 選出最多 3 條需要顯示右側標籤的線。
 *
 * 優先順序：
 *   1. 離最新收盤最近的靜態壓力（上方）
 *   2. 離最新收盤最近的靜態支撐（下方）
 *   3. 離最新收盤最近的動態均線（MA20 / MA60）
 *
 * 若兩條候選線的價格差距 < 1% × close，視為太接近，後加入的略去。
 *
 * 回傳：應顯示標籤的 label 集合（用原始 label 字串作 key）
 */
function selectLabeledLines(
  supportLines: SupportResistanceLine[],
  resistanceLines: SupportResistanceLine[],
  close: number,
): Set<string> {
  const PROX = close * 0.01   // 1% 近距離閾值

  const selected: Array<{ label: string; price: number }> = []

  function tryAdd(line: SupportResistanceLine) {
    for (const s of selected) {
      if (Math.abs(line.price - s.price) < PROX) return  // 太接近，略過
    }
    selected.push({ label: line.label, price: line.price })
  }

  // 1. 最近靜態壓力（close 上方，靜態線）
  const staticR = resistanceLines
    .filter(l => l.type === 'static' && l.price > close)
    .sort((a, b) => a.price - b.price)   // 最近 = 最小
  if (staticR[0]) tryAdd(staticR[0])

  // 2. 最近靜態支撐（close 下方，靜態線）
  const staticS = supportLines
    .filter(l => l.type === 'static' && l.price < close)
    .sort((a, b) => b.price - a.price)   // 最近 = 最大
  if (staticS[0]) tryAdd(staticS[0])

  // 3. 最近動態均線（MA20 / MA60，不限上下）
  const dynAll = [...supportLines, ...resistanceLines]
    .filter(l => l.type === 'dynamic')
    .sort((a, b) => Math.abs(a.price - close) - Math.abs(b.price - close))
  if (dynAll[0]) tryAdd(dynAll[0])

  return new Set(selected.map(s => s.label))
}

export default function StockChart({ data, trades = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const closesForLegend = useMemo(() => data.ohlcv.map(b => b.close), [data.ohlcv])
  const volumesForLegend = useMemo(() => data.ohlcv.map(b => b.volume), [data.ohlcv])
  const ma5Values = useMemo(() => computeMA(closesForLegend, 5), [closesForLegend])
  const ma10Values = useMemo(() => computeMA(closesForLegend, 10), [closesForLegend])
  const ma20Values = useMemo(() => computeMA(closesForLegend, 20), [closesForLegend])
  const ma60Values = useMemo(() => computeMA(closesForLegend, 60), [closesForLegend])
  const volMa5Values = useMemo(() => computeMA(volumesForLegend, 5), [volumesForLegend])
  const volMa10Values = useMemo(() => computeMA(volumesForLegend, 10), [volumesForLegend])
  const ma5Latest = latestValue(ma5Values)
  const ma10Latest = latestValue(ma10Values)
  const ma20Latest = latestValue(ma20Values)
  const ma60Latest = latestValue(ma60Values)
  const volMa5Latest = latestValue(volMa5Values)
  const volMa10Latest = latestValue(volMa10Values)
  const latestVolume = data.ohlcv.at(-1)?.volume ?? null
  const recentVolumeLow = useMemo(() => findRecentVolumeLow(data.ohlcv, 20), [data.ohlcv])
  const latestReadout = useMemo(() => {
    const lastDate = data.ohlcv.at(-1)?.date
    if (!lastDate) return null
    return buildReadout(data.ohlcv, lastDate, ma5Values, ma10Values, ma20Values, ma60Values, volMa5Values, volMa10Values)
  }, [data.ohlcv, ma5Values, ma10Values, ma20Values, ma60Values, volMa5Values, volMa10Values])
  const [hoverReadout, setHoverReadout] = useState<ChartReadout | null>(null)
  const readout = hoverReadout ?? latestReadout

  useEffect(() => {
    if (!containerRef.current || data.ohlcv.length === 0) return

    const container = containerRef.current
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: '#e0e0e0',
        scaleMargins: { top: 0.08, bottom: 0.28 },
      },
      timeScale: { borderColor: '#e0e0e0', timeVisible: true, rightOffset: 20 },
    })
    chartRef.current = chart

    // ── K線 (台股：漲紅跌綠) ──────────────────────────────────────────────
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#e84040',
      downColor: '#26a69a',
      borderUpColor: '#e84040',
      borderDownColor: '#26a69a',
      wickUpColor: '#e84040',
      wickDownColor: '#26a69a',
    } as Partial<CandlestickSeriesOptions>)

    const candleData = data.ohlcv.map(bar => ({
      time: bar.date as import('lightweight-charts').Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }))
    candleSeries.setData(candleData)

    const volumeSeries = chart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: true,
    } as Partial<HistogramSeriesOptions>)
    volumeSeries.setData(data.ohlcv.map(bar => ({
      time: bar.date as import('lightweight-charts').Time,
      value: bar.volume,
      color: bar.close >= bar.open ? 'rgba(232,64,64,0.55)' : 'rgba(38,166,154,0.55)',
    })))
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
      borderVisible: false,
    })

    const visibleDates = new Set(data.ohlcv.map(bar => bar.date))
    const tradeMarkers: SeriesMarker<import('lightweight-charts').Time>[] = trades
      .filter(t => t.stock_id === data.code && visibleDates.has(t.date))
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(t => ({
        time: t.date as import('lightweight-charts').Time,
        position: t.trade_type === 'buy' ? 'belowBar' : 'aboveBar',
        color: t.trade_type === 'buy' ? '#1565c0' : '#c62828',
        shape: t.trade_type === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${t.trade_type === 'buy' ? '買' : '賣'} ${t.price.toFixed(2)}`,
      }))

    const volumeLowMarkers: SeriesMarker<import('lightweight-charts').Time>[] =
      recentVolumeLow && visibleDates.has(recentVolumeLow.date)
        ? [{
            time: recentVolumeLow.date as import('lightweight-charts').Time,
            position: 'belowBar',
            color: '#1b5e20',
            shape: 'circle',
            text: `${recentVolumeLow.isExplosion ? '爆量低' : '大量低'} ${formatPrice(recentVolumeLow.price)}${recentVolumeLow.volumeRatio != null ? ` ${recentVolumeLow.volumeRatio}x` : ''}`,
          }]
        : []

    const markers = [...tradeMarkers, ...volumeLowMarkers]
      .sort((a, b) => String(a.time).localeCompare(String(b.time)))
    if (markers.length > 0) {
      candleSeries.setMarkers(markers)
    }

    // ── 均線 (MA5 / MA10 / MA20 / MA60) ───────────────────────────────────
    const dates  = data.ohlcv.map(b => b.date as import('lightweight-charts').Time)

    const maConfigs = [
      { period: 5,  color: '#f9a825', values: ma5Values },
      { period: 10, color: '#d9822b', values: ma10Values },
      { period: 20, color: '#fb8c00', values: ma20Values },
      { period: 60, color: '#1565c0', values: ma60Values },
    ]

    for (const { period, color, values } of maConfigs) {
      const maSeries = chart.addLineSeries({
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: `MA${period}`,
      } as Partial<LineSeriesOptions>)
      const maData = values
        .map((v, i) => v !== null ? { time: dates[i], value: v } : null)
        .filter((d): d is { time: import('lightweight-charts').Time; value: number } => d !== null)
      maSeries.setData(maData)
    }

    const volumeMaConfigs = [
      { period: 5, color: '#6b7280', values: volMa5Values },
      { period: 10, color: '#374151', values: volMa10Values },
    ]
    for (const { period, color, values } of volumeMaConfigs) {
      const volumeMaSeries = chart.addLineSeries({
        priceScaleId: 'volume',
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: `量MA${period}`,
      } as Partial<LineSeriesOptions>)
      const volumeMaData = values
        .map((v, i) => v !== null ? { time: dates[i], value: v } : null)
        .filter((d): d is { time: import('lightweight-charts').Time; value: number } => d !== null)
      volumeMaSeries.setData(volumeMaData)
    }

    // ── 決定哪些線需要右側標籤 ────────────────────────────────────────────
    const close = data.close ?? (data.ohlcv.at(-1)?.close ?? 0)
    const labeled = selectLabeledLines(data.support_lines, data.resistance_lines, close)

    // ── 支撐線 (綠虛線) ───────────────────────────────────────────────────
    for (const line of data.support_lines) {
      const showLabel = labeled.has(line.label)
      candleSeries.createPriceLine({
        price: line.price,
        color: '#2e7d32',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: showLabel,
        title: showLabel ? (SHORT_LABEL[line.label] ?? line.label) : '',
      })
    }

    // ── 壓力線 (紅虛線) ───────────────────────────────────────────────────
    for (const line of data.resistance_lines) {
      const showLabel = labeled.has(line.label)
      candleSeries.createPriceLine({
        price: line.price,
        color: '#c62828',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: showLabel,
        title: showLabel ? (SHORT_LABEL[line.label] ?? line.label) : '',
      })
    }

    // ── 趨勢線（延伸至最新 K 棒日期） ────────────────────────────────────
    const lastDate = data.ohlcv.at(-1)!.date
    const volumeLow = recentVolumeLow
    if (volumeLow) {
      const volumeLowSupport = chart.addLineSeries({
        color: '#1b5e20',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: true,
        title: volumeLow.isExplosion ? '爆量低' : '大量低',
      } as Partial<LineSeriesOptions>)
      volumeLowSupport.setData([
        { time: volumeLow.date as import('lightweight-charts').Time, value: volumeLow.price },
        { time: lastDate as import('lightweight-charts').Time, value: volumeLow.price },
      ])
    }

    // 延伸目標：最後 K 棒後約 14 個日曆天（≈10 個交易日），讓趨勢線進入右側空白區
    const extendTarget = (() => {
      const d = new Date(lastDate)
      d.setDate(d.getDate() + 14)
      return d.toISOString().slice(0, 10)
    })()

    if (data.uptrend_line.valid && data.uptrend_line.p1 && data.uptrend_line.p2) {
      const { p1, p2 } = data.uptrend_line
      const lineData: Array<{ time: import('lightweight-charts').Time; value: number }> = [
        { time: p1.date as import('lightweight-charts').Time, value: p1.price },
        { time: p2.date as import('lightweight-charts').Time, value: p2.price },
        { time: extendTarget as import('lightweight-charts').Time, value: extendTrendLine(p1, p2, extendTarget) },
      ]
      const tl = chart.addLineSeries({
        color: '#2e7d32',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
      } as Partial<LineSeriesOptions>)
      tl.setData(lineData)
    }

    if (data.downtrend_line.valid && data.downtrend_line.p1 && data.downtrend_line.p2) {
      const { p1, p2 } = data.downtrend_line
      const lineData: Array<{ time: import('lightweight-charts').Time; value: number }> = [
        { time: p1.date as import('lightweight-charts').Time, value: p1.price },
        { time: p2.date as import('lightweight-charts').Time, value: p2.price },
        { time: extendTarget as import('lightweight-charts').Time, value: extendTrendLine(p1, p2, extendTarget) },
      ]
      const tl = chart.addLineSeries({
        color: '#c62828',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
      } as Partial<LineSeriesOptions>)
      tl.setData(lineData)
    }

    chart.timeScale().fitContent()

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time) {
        setHoverReadout(null)
        return
      }
      const date = typeof param.time === 'string'
        ? param.time
        : typeof param.time === 'number'
          ? new Date(param.time * 1000).toISOString().slice(0, 10)
          : `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`
      setHoverReadout(buildReadout(
        data.ohlcv,
        date,
        ma5Values,
        ma10Values,
        ma20Values,
        ma60Values,
        volMa5Values,
        volMa10Values,
      ))
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    // ── resize handler ────────────────────────────────────────────────────
    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth })
    })
    observer.observe(container)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, ma5Values, ma10Values, ma20Values, ma60Values, volMa5Values, volMa10Values, recentVolumeLow])

  if (data.ohlcv.length === 0) {
    return <div className="chart-empty">無 K 棒資料</div>
  }

  return (
    <div className="chart-wrapper">
      <div className="chart-legend">
        <span className="legend-item" style={{ color: '#f9a825' }}>MA5 {formatPrice(ma5Latest)}</span>
        <span className="legend-item" style={{ color: '#d9822b' }}>MA10 {formatPrice(ma10Latest)}</span>
        <span className="legend-item" style={{ color: '#fb8c00' }}>MA20 {formatPrice(ma20Latest)}</span>
        <span className="legend-item" style={{ color: '#1565c0' }}>MA60 {formatPrice(ma60Latest)}</span>
        <span className="legend-item" style={{ color: '#555' }}>量 {formatVolume(latestVolume)}</span>
        <span className="legend-item" style={{ color: '#6b7280' }}>量MA5 {formatVolume(volMa5Latest)}</span>
        <span className="legend-item" style={{ color: '#374151' }}>量MA10 {formatVolume(volMa10Latest)}</span>
        {recentVolumeLow && (
          <span className="legend-item" style={{ color: '#1b5e20' }}>
            {recentVolumeLow.isExplosion ? '爆量低支撐' : '大量低支撐'} {formatPrice(recentVolumeLow.price)}
            {recentVolumeLow.volumeRatio != null ? ` (${recentVolumeLow.volumeRatio}x)` : ''}
          </span>
        )}
        <span className="legend-item" style={{ color: '#2e7d32' }}>支撐</span>
        <span className="legend-item" style={{ color: '#c62828' }}>壓力</span>
      </div>
      {readout && (
        <div className="chart-readout">
          <span>{readout.date}</span>
          <span>開 <strong>{formatPrice(readout.open)}</strong></span>
          <span>高 <strong>{formatPrice(readout.high)}</strong></span>
          <span>低 <strong>{formatPrice(readout.low)}</strong></span>
          <span>收 <strong>{formatPrice(readout.close)}</strong></span>
          <span>量 <strong>{formatVolume(readout.volume)}</strong></span>
          <span>MA5 <strong>{formatPrice(readout.ma5)}</strong></span>
          <span>MA10 <strong>{formatPrice(readout.ma10)}</strong></span>
          <span>MA20 <strong>{formatPrice(readout.ma20)}</strong></span>
          <span>MA60 <strong>{formatPrice(readout.ma60)}</strong></span>
          <span>量MA5 <strong>{formatVolume(readout.volMa5)}</strong></span>
          <span>量MA10 <strong>{formatVolume(readout.volMa10)}</strong></span>
        </div>
      )}
      <div ref={containerRef} className="chart-container" />
    </div>
  )
}
