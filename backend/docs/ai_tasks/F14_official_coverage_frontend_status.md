# F14 Official Coverage Frontend Status

Status: completed

## Goal

Show the official fundamentals coverage audit in Dashboard / PM-facing UI without recreating backend rules.

Hard rules:

* Frontend only consumes `GET /api/system/fundamentals-official/coverage-audit`.
* Frontend must not recompute coverage, strategy, score, recommendation buckets, or fundamentals rules.
* Do not write `fundamentals.csv`, `fundamentals.json`, priority CSV, trades, holdings, or cash.
* Do not fill `dividend_years`, growth CAGR, ROE, FCF, or any derived formal field.

## Tasks

1. Frontend API/type contract
   - Status: done
   - Add client method and TypeScript shape for the coverage audit response.

2. Structure test
   - Status: done
   - Add or update frontend structure test to assert the UI consumes the backend endpoint.

3. Dashboard rendering
   - Status: done
   - Show compact status: target count, coverage percent, missing official reports, and next action.

4. Verification
   - Status: done
   - Run frontend structure tests and build.

## Output

Dashboard / PM-facing UI now shows:

* official coverage target count
* backend-provided coverage percent
* missing official report files
* backend-provided next action

The frontend calls:

```text
GET /api/system/fundamentals-official/coverage-audit
```

If the endpoint returns 404, the UI shows a readable missing-state message and does not generate or modify files.

## Verification

Passed:

```bash
node --test frontend/tests/*.test.mjs
npm run build
```

Build still has the existing Vite chunk-size warning.

## Acceptance

* User can see whether official report-only data covers priority stocks.
* Missing priority CSV or audit endpoint errors are shown as status, not silent failure.
* No frontend strategy or fundamentals computation is introduced.
