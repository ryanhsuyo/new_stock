import type { DailyBrief, ManualWatchlistReview } from '../types'
import { BRIEF_BUCKETS, BriefStockList, ManualWatchlistReviewPanel, TomorrowTaskList } from './DailyBriefParts'

interface DailyBriefBoxProps {
  brief: DailyBrief | null
  manualReview: ManualWatchlistReview | null
  running: boolean
  onNavigateAnalysis?: (code: string) => void
}

export default function DailyBriefBox({
  brief,
  manualReview,
  running,
  onNavigateAnalysis,
}: DailyBriefBoxProps) {
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

          <ManualWatchlistReviewPanel review={effectiveManualReview} onAnalysis={onNavigateAnalysis} />

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
