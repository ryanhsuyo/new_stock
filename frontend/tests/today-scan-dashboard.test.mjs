import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')

test('dashboard renders backend-owned Today Scan summary without recomputing strategy', () => {
  assert.match(dashboard, /TodayScanReport/)
  assert.match(dashboard, /const \[todayScan, setTodayScan\]/)
  assert.match(dashboard, /api\.getTodayScanOrNull\(\)/)
  assert.match(dashboard, /setTodayScan\(scan\)/)
  assert.match(dashboard, /todayScan=\{todayScan\}/)
  assert.match(dashboard, /today-scan-quick-card/)
  assert.match(dashboard, /strategy_score_summary\?\.summary_label/)
  assert.match(dashboard, /today-scan-freshness/)
  assert.match(dashboard, /data_freshness/)
  assert.match(dashboard, /usage_status/)
  assert.match(dashboard, /today-scan-usage-status/)
  assert.match(dashboard, /can_use_trade_outputs/)
  assert.match(dashboard, /stale_count/)
  assert.match(dashboard, /missing_date_count/)
  assert.match(dashboard, /top_stale_items/)
  assert.match(dashboard, /formal_entries\.length/)
  assert.match(dashboard, /old_wang_candidates\.length/)
  assert.match(dashboard, /steady_momentum_candidates\.length/)
  assert.doesNotMatch(dashboard, /computeTodayScan/)
  assert.doesNotMatch(dashboard, /calculateTodayScan/)
  assert.doesNotMatch(dashboard, /computeTodayScanFreshness/)
})
