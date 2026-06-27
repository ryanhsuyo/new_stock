interface DecisionStatusStripProps {
  dataAsOf: string | null
  rawAsOf: string | null
  canUseTradeOutputs: boolean
  statusLabel: string
  priceBasisLabel: string
  lastUpdatedAt: string | null
  isStale: boolean
  staleDays?: number | null
}

export default function DecisionStatusStrip({
  dataAsOf,
  rawAsOf,
  canUseTradeOutputs,
  statusLabel,
  priceBasisLabel,
  lastUpdatedAt,
  isStale,
  staleDays,
}: DecisionStatusStripProps) {
  return (
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
        <strong>{priceBasisLabel}</strong>
        <em>非即時市價</em>
      </div>
      <div>
        <span>最後更新</span>
        <strong>{lastUpdatedAt ?? '—'}</strong>
        {isStale && <em>已 {staleDays ?? '?'} 天未更新</em>}
      </div>
    </div>
  )
}
