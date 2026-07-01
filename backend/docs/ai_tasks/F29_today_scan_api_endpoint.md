# F29 Today Scan API Endpoint

## Goal

Expose the existing `backend/out/today_scan.json` through a read-only API so frontend/product surfaces can consume the same two-strategy scan report as CLI and Daily Check.

## Scope

Allowed:

* Add `GET /api/system/today-scan`.
* Return the existing report from `today_scan_service.load_today_scan_report`.
* Return a clear 404 when `today_scan.json` does not exist.
* Add focused API tests and docs/state updates.

Not allowed:

* Recalculate Today Scan in the router.
* Write or regenerate `backend/out/*` from the endpoint.
* Add strategy buckets or change strategy scoring.
* Modify trades, holdings, cash, or formal trading records.

## Checklist

* [x] Add failing API tests.
* [x] Add minimal router endpoint.
* [x] Run focused API tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_api.py -q`
* `git diff --check`

## Result

Completed. `GET /api/system/today-scan` now exposes the existing Today Scan report as a read-only API and returns 404 when the report is missing.
