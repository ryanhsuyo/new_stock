# F22 Daily Check Data Freshness Action

Status: completed

Purpose:

Promote partial stale universe rows from a hidden Today Scan detail into an explicit Daily Check product-health action.

## Context

F19 added `today_scan.data_freshness`, and Daily Check already includes stale-row preview text inside the Today Scan action. The current product gap is that stale rows are still secondary to scan buckets. A user opening the system should see data freshness as a first-class health item with a clear refresh command.

## Scope

Add a small Daily Check action when `today_scan.data_freshness.stale_count` or `missing_date_count` is non-zero:

* key: `data_freshness`
* status: `warn`
* title: `追蹤股票資料日落後`
* next action: run the normal one-month daily update
* payload: command with copy command and expected outputs
* preview: stale stock labels from `top_stale_items`

Keep Today Scan action intact as the scan summary.

## Guardrails

* Do not change strategy scoring.
* Do not update OHLCV or generated out files by hand.
* Do not modify trades, holdings, cash, or formal personal records.
* Router remains untouched.

## Acceptance

* Daily Check tests cover the new `data_freshness` action.
* Focused Daily Check tests pass.
* `ai_execution_plan.md` and `loop_state.md` reflect F22 completion or next state.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q` passed, 22 tests.
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/daily_check.py --write-report` produced the expected WARN report and wrote `backend/out/daily_check.json`.
