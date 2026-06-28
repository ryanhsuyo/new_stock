import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')

test('frontend has an official fundamentals status contract and API client', () => {
  assert.match(types, /export interface OfficialFundamentalsStatus/)
  assert.match(types, /export interface OfficialFundamentalsReportStatus/)
  assert.match(client, /getOfficialFundamentalsStatus/)
  assert.match(client, /\/system\/fundamentals-official\/status/)
})

test('dashboard consumes official fundamentals status without creating a new strategy bucket', () => {
  assert.match(dashboard, /officialFundamentalsStatus/)
  assert.match(dashboard, /getOfficialFundamentalsStatus/)
  assert.match(dashboard, /官方基本面報告/)
  assert.match(dashboard, /report-only/)

  const strategyOptionsBlock = dashboard.match(/const STRATEGY_OPTIONS:[\s\S]*?\n\]/)?.[0] ?? ''
  assert.doesNotMatch(strategyOptionsBlock, /official/)
  assert.doesNotMatch(strategyOptionsBlock, /fundamentals/)
})
