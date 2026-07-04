import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')

test('frontend exposes a read-only Today Scan API contract', () => {
  assert.match(client, /TodayScanReport/)
  assert.match(client, /getTodayScanOrNull/)
  assert.match(client, /\/system\/today-scan/)
  assert.match(client, /catch\(\(\) => null as TodayScanReport \| null\)/)

  assert.match(types, /export interface TodayScanStrategyScoreSummary/)
  assert.match(types, /primary_strategy: 'old_wang' \| 'steady_momentum' \| 'none' \| string/)
  assert.match(types, /summary_label: string/)
  assert.match(types, /export interface TodayScanItem/)
  assert.match(types, /strategy_score_summary\?: TodayScanStrategyScoreSummary/)
  assert.match(types, /export interface TodayScanUsageStatus/)
  assert.match(types, /export interface TodayScanReport/)
  assert.match(types, /formal_entries: TodayScanItem\[\]/)
  assert.match(types, /old_wang_candidates: TodayScanItem\[\]/)
  assert.match(types, /steady_momentum_candidates: TodayScanItem\[\]/)
  assert.match(types, /risk_items: TodayScanItem\[\]/)
  assert.match(types, /usage_status\?: TodayScanUsageStatus/)
})
