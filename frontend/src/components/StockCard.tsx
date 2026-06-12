import type { KeyboardEvent } from 'react'
import type { StockRecommendation } from '../types'
import DailyChecklist from './DailyChecklist'

interface Props {
  stock: StockRecommendation
  onBuy: (stock: StockRecommendation) => void
  onAnalysis?: (code: string) => void
}

function scoreColor(score: number): string {
  if (score >= 85) return 'score-high'
  if (score >= 70) return 'score-mid'
  return 'score-low'
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

export default function StockCard({ stock, onBuy, onAnalysis }: Props) {
  const updown = stock.change_pct > 0 ? 'up' : stock.change_pct < 0 ? 'down' : 'flat'
  const sign = stock.change_pct > 0 ? '+' : ''
  const openAnalysis = () => onAnalysis?.(stock.stock_id)
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
          <span className="stock-name">{stock.name}</span>
          <span className="stock-id">{stock.stock_id}</span>
        </div>
        <span className={`score-badge ${scoreColor(stock.score)}`}>
          {stock.score} 分
        </span>
      </div>

      <div className="stock-price-row">
        <span className="stock-price">{stock.price.toFixed(2)}</span>
        <span className={`stock-change ${updown}`}>
          {sign}{stock.change_pct.toFixed(2)}%
        </span>
      </div>
      {stock.position_size_pct != null && (
        <div className="position-hint">
          建議倉位 <strong>{stock.position_size_pct}%</strong>
          {stock.position_size_note && <span>{stock.position_size_note}</span>}
        </div>
      )}

      {stock.old_wang_badges?.length > 0 && (
        <div className="strategy-badges" aria-label="老王策略條件">
          <span className="strategy-badge strategy-badge-source">
            老王
            {stock.old_wang_score != null ? ` ${stock.old_wang_score}` : ''}
          </span>
          {stock.old_wang_badges.map(badge => (
            <span className="strategy-badge" key={badge}>{badge}</span>
          ))}
        </div>
      )}

      {stock.recommendation_source === 'buffett' && (
        <div className="strategy-badges" aria-label="巴菲特品質價值條件">
          <span className="strategy-badge strategy-badge-source">
            巴菲特{stock.buffett_score != null ? ` ${stock.buffett_score}` : ''}
          </span>
          {stock.buffett_quality_score != null && <span className="strategy-badge">品質 {stock.buffett_quality_score}</span>}
          {stock.buffett_safety_score != null && <span className="strategy-badge">安全 {stock.buffett_safety_score}</span>}
          {stock.buffett_value_score != null && <span className="strategy-badge">估值 {stock.buffett_value_score}</span>}
        </div>
      )}

      <p className="stock-reason">{stock.reason}</p>

      <DailyChecklist items={stock.daily_checklist} compact />

      <div className="chip-grid" aria-label="籌碼摘要">
        <div className="chip-item">
          <span className="chip-label">外資</span>
          <span className="chip-value">{fmtChipLots(stock.chip.foreign_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">投信</span>
          <span className="chip-value">{fmtChipLots(stock.chip.investment_trust_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">散戶≤100張</span>
          <span className="chip-value">{fmtChipPct(stock.chip.retail_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">大戶≥400張</span>
          <span className="chip-value">{fmtChipPct(stock.chip.major_investor_net_buy)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">成交量</span>
          <span className="chip-value">{fmtVolume(stock.volume)}</span>
        </div>
        <div className="chip-item">
          <span className="chip-label">量比</span>
          <span className="chip-value">{stock.vol_ratio != null ? `${stock.vol_ratio.toFixed(2)}x` : '—'}</span>
        </div>
        {stock.chip.data_as_of && (
          <span className="chip-date">
            法人日 {stock.chip.data_as_of}
            {stock.chip.holder_data_as_of ? ` · 集保日 ${stock.chip.holder_data_as_of}` : ''}
          </span>
        )}
      </div>

      <div className="stock-risk">
        <span className="risk-icon">⚠</span>
        {stock.risk_warning}
      </div>

      <div className="stock-card-actions">
        {onAnalysis && (
          <button
            className="btn btn-ghost"
            onClick={e => { e.stopPropagation(); openAnalysis() }}
            title="查看技術分析圖"
          >
            查看線圖
          </button>
        )}
        <button className="btn btn-primary" onClick={e => { e.stopPropagation(); onBuy(stock) }}>
          記錄買入
        </button>
      </div>
    </div>
  )
}
