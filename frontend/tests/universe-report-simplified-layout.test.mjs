import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const universeReport = readFileSync(new URL('../src/pages/UniverseReportPage.tsx', import.meta.url), 'utf8')

test('universe report moves secondary controls into a collapsed advanced section', () => {
  assert.match(universeReport, /<details className="report-advanced-section">/)
  assert.match(universeReport, /進階篩選與復盤/)
  assert.match(universeReport, /journal-progress-board/)
  assert.match(universeReport, /price-position-board/)
  assert.match(universeReport, /daily-decision-board/)

  const advancedBlock = universeReport.match(/<details className="report-advanced-section">[\s\S]*?<\/details>/)?.[0] ?? ''
  assert.match(advancedBlock, /journal-progress-board/)
  assert.match(advancedBlock, /price-position-board/)
  assert.match(advancedBlock, /daily-decision-board/)
})
