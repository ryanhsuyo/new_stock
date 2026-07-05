import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')

test('pm worklist can acknowledge backend-owned signal alerts review action', () => {
  assert.match(client, /acknowledgeSignalAlerts/)
  assert.match(client, /\/system\/signal-alert-reviews\/current/)
  assert.match(types, /SignalAlertReviewStatus/)
  assert.match(dashboard, /handleAcknowledgeSignalAlerts/)
  assert.match(dashboard, /api\.acknowledgeSignalAlerts/)
  assert.match(dashboard, /payload\?\.endpoint === '\/api\/system\/signal-alert-reviews\/current'/)
  assert.match(dashboard, /onAcknowledgeSignalAlerts/)
  assert.match(dashboard, /DecisionConsole[\s\S]*onAcknowledgeSignalAlerts/)
  assert.match(dashboard, /primaryAction\.action_payload/)
  assert.doesNotMatch(dashboard, /signal_alerts[\s\S]{0,200}can_use_trade_outputs\s*=/)
})
