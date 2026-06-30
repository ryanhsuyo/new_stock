import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const universeReport = readFileSync(new URL('../src/pages/UniverseReportPage.tsx', import.meta.url), 'utf8')

test('universe report top quick card clearly filters to only small-trial entries', () => {
  assert.match(universeReport, /showDecisionFilter\('enter'\)/)
  assert.match(universeReport, /只看可小試/)
  assert.match(universeReport, /decisionFilter === action/)
  assert.match(universeReport, /今日動作：可小試/)

  assert.match(universeReport, /className=\{reportHealthActionClass\('enter'\)\}/)

  const smallTrialCard = universeReport.match(/className=\{reportHealthActionClass\('enter'\)\}[\s\S]*?<\/button>/)?.[0] ?? ''
  assert.match(smallTrialCard, /reportHealthActionClass\('enter'\)/)
  assert.doesNotMatch(smallTrialCard, /entryRangeCount/)
})
