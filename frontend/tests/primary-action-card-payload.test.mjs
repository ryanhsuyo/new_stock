import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const primaryActionCard = readFileSync(new URL('../src/components/PrimaryActionCard.tsx', import.meta.url), 'utf8')

test('primary action card shows backend-owned payload context', () => {
  assert.match(primaryActionCard, /primaryAction\?\.action_payload/)
  assert.match(primaryActionCard, /file_path/)
  assert.match(primaryActionCard, /preview_items/)
  assert.match(primaryActionCard, /expected_outputs/)
  assert.match(primaryActionCard, /primary-action-payload/)
  assert.match(primaryActionCard, /primary-action-preview/)
  assert.doesNotMatch(primaryActionCard, /computePrimaryAction/)
  assert.doesNotMatch(primaryActionCard, /sort\(/)
})
