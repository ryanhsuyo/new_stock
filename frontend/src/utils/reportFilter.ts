import type { UniverseReportItem } from '../types'

export type SignalFilter =
  | 'all'
  | 'entry_confirmed'
  | 'ready_to_enter'
  | 'watchlist'
  | 'hold'
  | 'take_profit_warning'
  | 'exit_warning'
  | 'invalidated'
  | 'DATA_MISSING'

export type MarketFilter = 'all' | 'TWSE' | 'TPEX' | 'ETF'
export type PlanFilter = 'all' | 'core' | 'old_wang' | 'buffett' | 'confluence' | 'no_entry'
export type HoldingFilter = 'all' | 'holding' | 'not_holding'

export function hasOldWangTag(item: UniverseReportItem): boolean {
  return item.old_wang_flag === true || item.old_wang_tag === 'old_wang_market_chip_rotation'
}

export function hasCoreEntry(item: UniverseReportItem): boolean {
  return item.internal_signal === 'entry_confirmed' || item.internal_signal === 'ready_to_enter'
}

export function resolvePlan(item: UniverseReportItem): Exclude<PlanFilter, 'all'> {
  const core = hasCoreEntry(item)
  const oldWang = hasOldWangTag(item)
  if (core && oldWang) return 'confluence'
  if (core) return 'core'
  if (oldWang) return 'old_wang'
  if (item.buffett_flag) return 'buffett'
  return 'no_entry'
}

/**
 * 台灣股市市場推斷（近似，以代碼前綴判斷）
 * 0xxx / 00xxx / 006xxx → ETF
 * 1xxx / 2xxx           → TWSE 上市
 * 其餘                  → TPEX 上櫃
 */
export function inferMarket(code: string): 'TWSE' | 'TPEX' | 'ETF' {
  if (code.startsWith('0')) return 'ETF'
  const first = code[0]
  if (first === '1' || first === '2') return 'TWSE'
  return 'TPEX'
}

/**
 * 取得該 item 的 market（前端篩選用）。
 * 優先使用 API 回傳的 item.market，若為空才用 inferMarket() 備援。
 */
export function resolveMarket(item: UniverseReportItem): string {
  return item.market || inferMarket(item.code)
}

export function isHolding(item: UniverseReportItem): boolean {
  return (item.holding_shares ?? 0) > 0
}

/** 根據篩選條件過濾 universe report 清單（純函式，可獨立測試） */
export function filterReport(
  items: UniverseReportItem[],
  signal: SignalFilter,
  market: MarketFilter,
  plan: PlanFilter,
  holding: HoldingFilter,
  keyword: string,
): UniverseReportItem[] {
  const kw = keyword.trim().toLowerCase()
  return items.filter(item => {
    if (signal !== 'all' && item.internal_signal !== signal) return false
    if (market !== 'all' && resolveMarket(item) !== market) return false
    if (plan !== 'all' && resolvePlan(item) !== plan) return false
    if (holding === 'holding' && !isHolding(item)) return false
    if (holding === 'not_holding' && isHolding(item)) return false
    if (kw && !item.code.toLowerCase().includes(kw) && !item.name.toLowerCase().includes(kw)) return false
    return true
  })
}
