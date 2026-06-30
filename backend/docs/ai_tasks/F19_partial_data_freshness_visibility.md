# F19 Partial Data Freshness Visibility

Status: done

## Goal

Make partial stale stock rows visible in the daily product workflow.

## Context

The system output for 2026-06-30 was current overall, but `universe_report.csv`
contained a small number of rows whose `data_as_of` lagged the summary date.
Today Scan already had a note, but Daily Check did not expose the stale stock
sample in its primary action preview.

## Guardrails

* Do not change strategy logic.
* Do not change recommendation buckets.
* Do not modify trades, holdings, cash, or formal personal records.
* Keep this as read-only product observability.

## Changes

1. Added `today_scan.data_freshness` with row counts, date distribution, stale count, and top stale items.
2. Added partial stale row preview to the Daily Check `today_scan` action.
3. Covered the behavior with focused Today Scan and Daily Check tests.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py backend/tests/test_daily_check.py -q`

## Result

Daily Check can now tell the user which stock rows are lagging without forcing
them to inspect raw JSON.
