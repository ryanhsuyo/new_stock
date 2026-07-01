# F31 Dashboard Today Scan Summary Card

## Goal

Surface the backend-owned Today Scan report in the Dashboard decision console with minimal UI.

## Scope

Allowed:

* Fetch Today Scan through `api.getTodayScanOrNull()`.
* Pass the report into `DecisionConsole`.
* Render a small summary card with counts and the first formal entry's `strategy_score_summary.summary_label`.
* Add frontend structure tests and state docs.

Not allowed:

* Recalculate Today Scan buckets in frontend.
* Add new strategy buckets or change scoring.
* Modify trades, holdings, cash, or formal trading records.

## Checklist

* [x] Add failing frontend structure test.
* [x] Add minimal Dashboard state/fetch/rendering.
* [x] Run focused/all frontend structure tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `node --test frontend/tests/today-scan-dashboard.test.mjs`
* `node --test frontend/tests/*.test.mjs`
* `git diff --check`

## Result

Completed. Dashboard Decision Console now displays a small Today Scan summary card using only backend-provided `TodayScanReport` data.
