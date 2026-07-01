import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const stocksPage = readFileSync(new URL('../src/pages/StocksPage.tsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')

test('recommendation page is labeled as weekly while daily changes point to scan reports', () => {
  assert.match(app, /label: '本週推薦'/)
  assert.doesNotMatch(app, /label: '推薦清單'/)

  assert.match(stocksPage, /本週推薦/)
  assert.match(stocksPage, /每日盤後掃描/)
  assert.match(stocksPage, /正式推薦以週為單位/)
  assert.match(stocksPage, /Today Scan/)
  assert.match(css, /\.weekly-recommendation-note/)
})
