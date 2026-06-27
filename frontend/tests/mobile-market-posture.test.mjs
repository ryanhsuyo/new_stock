import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const component = readFileSync(new URL('../src/components/MarketPostureCard.tsx', import.meta.url), 'utf8')
const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')

test('MarketPostureCard supports desktop card and mobile disclosure variants', () => {
  assert.match(component, /variant\?: 'card' \| 'disclosure'/)
  assert.match(component, /<details className=\{`market-posture-mobile/)
  assert.match(component, /market-posture-desktop/)
})

test('Decision Console renders the disclosure after its desktop grid', () => {
  assert.match(dashboard, /variant="card"/)
  assert.match(
    dashboard,
    /<\/div>\s*<MarketPostureCard\s+variant="disclosure"/,
  )
})

test('phone CSS swaps the desktop card for the collapsed disclosure', () => {
  assert.match(css, /\.market-posture-mobile\s*{[^}]*display:\s*none;/s)

  const phoneMarker = '@media (max-width: 560px)'
  const desktopRule = css.indexOf('.market-posture-desktop {')
  const phoneStart = css.lastIndexOf(phoneMarker, desktopRule)
  const nextMedia = css.indexOf('@media ', phoneStart + phoneMarker.length)

  assert.ok(phoneStart >= 0, 'desktop hide rule must follow a 560px media query')
  assert.ok(nextMedia === -1 || desktopRule < nextMedia, 'desktop hide rule must stay inside the phone media block')
  assert.match(css.slice(desktopRule), /\.market-posture-desktop\s*{[^}]*display:\s*none;/s)
  assert.match(css.slice(desktopRule), /\.market-posture-mobile\s*{[^}]*display:\s*block;/s)
})
