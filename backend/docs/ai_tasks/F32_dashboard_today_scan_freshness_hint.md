# F32 Dashboard Today Scan Freshness Hint

## Goal

Make the Dashboard Today Scan card show backend-owned data freshness warnings so users can see when daily candidates include stale rows.

## Scope

Allowed:

* Read `TodayScanReport.data_freshness` from the existing frontend API contract.
* Display stale / missing-date counts and the first stale stock on the Dashboard Today Scan card.
* Add minimal frontend structure tests.
* Update docs and loop state.

Not allowed:

* Recalculate freshness in the frontend.
* Modify Today Scan buckets, scores, strategies, or backend signal logic.
* Modify trades, holdings, cash, or formal trading records.
* Write generated `backend/out/*` files manually.

## Checklist

* [x] Add failing frontend structure test.
* [x] Add typed `data_freshness` contract and minimal Dashboard rendering.
* [x] Run focused/all frontend structure tests and build.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `node --test frontend/tests/today-scan-dashboard.test.mjs`
* `node --test frontend/tests/*.test.mjs`
* `npm run build`
* `git diff --check`

## Result

Completed. Dashboard Today Scan now shows backend-owned stale / missing-date freshness warnings without recomputing scan buckets or strategy logic.
