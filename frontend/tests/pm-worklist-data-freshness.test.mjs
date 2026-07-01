import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const types = readFileSync(new URL('../src/types/index.ts', import.meta.url), 'utf8')

test('pm worklist groups data freshness with data repair health tasks', () => {
  assert.match(dashboard, /item\.action_type === 'data_repair'\s*\|\|\s*item\.action_type === 'data_freshness'/)
  assert.match(dashboard, /return \{ key: 'blockers', label: '阻塞 \/ 資料修復' \}/)
  assert.doesNotMatch(dashboard, /item\.action_type === 'data_freshness'[\s\S]{0,120}label: 'Daily Check'/)
  assert.match(types, /'data_repair' \| 'data_freshness' \| 'fundamentals'/)
})
