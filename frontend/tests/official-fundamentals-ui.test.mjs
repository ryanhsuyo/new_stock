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

test('dashboard can trigger official fundamentals report-only generation safely', () => {
  assert.match(client, /runOfficialFundamentalsReports/)
  assert.match(client, /method:\s*'POST'/)
  assert.match(client, /\/system\/fundamentals-official\/reports/)

  assert.match(dashboard, /handleRunOfficialFundamentalsReports/)
  assert.match(dashboard, /runOfficialFundamentalsReports\(\{ apply: false \}\)/)
  assert.match(dashboard, /產生官方 report-only CSV/)
  assert.match(dashboard, /不會 apply 到策略輸入/)
  assert.match(dashboard, /setOfficialFundamentalsStatus/)
})

test('dashboard displays official coverage audit as backend-owned status', () => {
  assert.match(types, /export interface OfficialFundamentalsCoverageAudit/)
  assert.match(client, /getOfficialFundamentalsCoverageAuditOrNull/)
  assert.match(client, /\/system\/fundamentals-official\/coverage-audit/)

  assert.match(dashboard, /officialCoverageAudit/)
  assert.match(dashboard, /getOfficialFundamentalsCoverageAuditOrNull/)
  assert.match(dashboard, /官方覆蓋率稽核/)
  assert.match(dashboard, /missing_report_files/)
  assert.doesNotMatch(dashboard, /calculateOfficialCoverage/)
  assert.doesNotMatch(dashboard, /computeOfficialCoverage/)

  const strategyOptionsBlock = dashboard.match(/const STRATEGY_OPTIONS:[\s\S]*?\n\]/)?.[0] ?? ''
  assert.doesNotMatch(strategyOptionsBlock, /official/)
  assert.doesNotMatch(strategyOptionsBlock, /coverage/)
})
