import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')
const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const universeReport = readFileSync(new URL('../src/pages/UniverseReportPage.tsx', import.meta.url), 'utf8')

test('recommendation strategy type exposes only the two product strategies', () => {
  const legacyStrategy = 'buf' + 'fett'
  assert.match(types, /export type RecommendationStrategy = 'steady_momentum' \| 'old_wang'/)
  assert.doesNotMatch(types, /export type RecommendationStrategy = .*'core'/)
  assert.doesNotMatch(types, new RegExp(`export type RecommendationStrategy = .*'${legacyStrategy}'`))
})

test('dashboard strategy selector shows only steady momentum and old wang', () => {
  const legacyStrategy = 'buf' + 'fett'
  assert.match(dashboard, /key: 'steady_momentum', label: '穩健動能'/)
  assert.match(dashboard, /key: 'old_wang', label: '老王短波段'/)

  const optionsBlock = dashboard.match(/const STRATEGY_OPTIONS:[\s\S]*?\n\]/)?.[0] ?? ''
  assert.doesNotMatch(optionsBlock, /core/)
  assert.doesNotMatch(optionsBlock, new RegExp(legacyStrategy))
})

test('universe report recommendation plan does not promote internal core signals', () => {
  assert.doesNotMatch(universeReport, /hasCoreEntry/)
  assert.doesNotMatch(universeReport, /coreBuy/)
})
