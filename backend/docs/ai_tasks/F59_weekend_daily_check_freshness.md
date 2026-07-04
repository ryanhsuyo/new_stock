# F59 Weekend Daily Check Freshness

Status: completed

Purpose:

Avoid false "refresh Daily Check" workflow warnings on weekends or non-trading days when outputs already cover the latest completed trading day.

## Scope

Allowed:

* Make Daily Check snapshot freshness use the expected completed trading day instead of raw calendar date.
* Add focused tests for weekend freshness.
* Update current rules and loop state.

Not allowed:

* Do not run long data update jobs.
* Do not edit generated `backend/out/*` manually.
* Do not modify trades, holdings, cash, or strategy logic.

## Tasks

1. Status: done — Add RED test for weekend Daily Check freshness.
2. Status: done — Implement trading-day-aware snapshot freshness.
3. Status: done — Run focused Daily Check / Update Workflow tests.
4. Status: done — Complete docs, update loop state, and commit if changed.

## Acceptance

* A Daily Check generated for the latest completed trading day remains fresh during the weekend.
* A Daily Check older than the latest completed trading day is stale.
* Update Workflow avoids weekend-only refresh noise while preserving real stale snapshot warnings.

## Verification

* RED check failed before implementation: weekend Daily Check generated on Friday was marked stale on Sunday.
* Focused Daily Check service tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_service_marks_old_snapshot_as_stale backend/tests/test_daily_check.py::test_daily_check_service_keeps_current_snapshot_fresh backend/tests/test_daily_check.py::test_daily_check_service_keeps_latest_trading_day_snapshot_fresh_on_weekend -q` (`3 passed`).
* Focused Update Workflow stale snapshot test passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py::test_update_workflow_warns_when_daily_check_snapshot_is_stale -q` (`1 passed`).
* Real service check now reports `snapshot_is_stale=false` and keeps Update Workflow on `signal_alerts` blocker instead of weekend-only `refresh_daily_check`.
