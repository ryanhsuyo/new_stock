import type { TodayFocusItem } from '../types'

interface TodayFocusCardsProps {
  portfolioFocus: TodayFocusItem[]
  followupFocus: TodayFocusItem[]
  onNavigateAnalysis?: (code: string) => void
  onFocusDecisionJournal: () => void
}

export default function TodayFocusCards({
  portfolioFocus,
  followupFocus,
  onNavigateAnalysis,
  onFocusDecisionJournal,
}: TodayFocusCardsProps) {
  return (
    <>
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
                <span className="decision-focus-main">
                  <b>{item.name}{item.code ? ` ${item.code}` : ''}</b>
                  <small>{item.short_reason || item.label}</small>
                </span>
                <em>{item.primary_metric || item.label}</em>
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
                <span className="decision-focus-main">
                  <b>{item.name}{item.code ? ` ${item.code}` : ''}</b>
                  <small>{item.short_reason || item.label}</small>
                </span>
                <em>{item.primary_metric || item.label}</em>
              </button>
            ))}
          </div>
        ) : (
          <p>目前沒有候選或復盤焦點。</p>
        )}
      </div>
    </>
  )
}
