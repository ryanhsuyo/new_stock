import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const updateWorkflowBox = readFileSync(new URL('../src/components/UpdateWorkflowBox.tsx', import.meta.url), 'utf8')

test('dashboard exposes a post-close one-click update action backed by the system API', () => {
  assert.match(client, /triggerUpdateNow/)
  assert.match(client, /\/system\/update-now/)
  assert.match(client, /method:\s*'POST'/)

  assert.match(dashboard, /handleUpdateNow/)
  assert.match(dashboard, /api\.triggerUpdateNow\(\)/)
  assert.match(dashboard, /盤後一鍵更新/)
  assert.match(dashboard, /onDailyUpdate=\{handleUpdateNow\}/)
})

test('update workflow card can trigger update without owning strategy logic', () => {
  assert.match(updateWorkflowBox, /onDailyUpdate/)
  assert.match(updateWorkflowBox, /盤後一鍵更新/)
  assert.match(updateWorkflowBox, /daily_update\.py --months 1/)
  assert.doesNotMatch(updateWorkflowBox, /runDailySignals/)
  assert.doesNotMatch(updateWorkflowBox, /calculateScore/)
  assert.doesNotMatch(updateWorkflowBox, /computeStrategy/)
})
