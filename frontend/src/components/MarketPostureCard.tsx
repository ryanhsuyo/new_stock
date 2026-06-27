interface MarketPostureCardProps {
  variant?: 'card' | 'disclosure'
  isStale: boolean
  title: string
  reason: string
  riskLevel: string
  source?: string | null
  noteStatusLabel?: string | null
  noteDate?: string | null
  appliesToAsOf?: string | null
  focusSectors: string[]
  onFocusMarketNote: () => void
}

export default function MarketPostureCard({
  variant = 'card',
  isStale,
  title,
  reason,
  riskLevel,
  source,
  noteStatusLabel,
  noteDate,
  appliesToAsOf,
  focusSectors,
  onFocusMarketNote,
}: MarketPostureCardProps) {
  const content = (
    <>
      <p title={reason}>{reason}</p>
      <div className="decision-console-meta">
        <em>{riskLevel}</em>
        {source && <em>{source}</em>}
        {noteStatusLabel && <em>{noteStatusLabel}</em>}
        {noteDate && <em>筆記 {noteDate}</em>}
        {appliesToAsOf && <em>適用 {appliesToAsOf}</em>}
        {isStale && <button className="btn btn-ghost btn-xs" onClick={onFocusMarketNote}>更新筆記</button>}
      </div>
      {focusSectors.length > 0 && (
        <div className="decision-console-tags">
          {focusSectors.map(sector => <b key={sector}>{sector}</b>)}
        </div>
      )}
    </>
  )

  if (variant === 'disclosure') {
    return (
      <details className={`market-posture-mobile ${isStale ? 'stale' : ''}`}>
        <summary>
          <span>大盤姿態</span>
          <strong>{title}</strong>
        </summary>
        <div className="market-posture-mobile-body">{content}</div>
      </details>
    )
  }

  return (
    <div className={`market-posture-desktop decision-console-card market ${isStale ? 'stale' : ''}`}>
      <span>大盤姿態</span>
      <strong>{title}</strong>
      {content}
    </div>
  )
}
