import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')

test('pm worklist renders backend-owned signal alert preview alerts', () => {
  assert.match(types, /preview_alerts\?:/)
  assert.match(types, /review_focus: string\[\]/)
  assert.match(dashboard, /renderPreviewAlerts/)
  assert.match(dashboard, /action_payload\?\.preview_alerts/)
  assert.match(dashboard, /pm-worklist-alert-preview/)
  assert.doesNotMatch(dashboard, /preview_alerts[\s\S]{0,160}\.sort\(/)
})
