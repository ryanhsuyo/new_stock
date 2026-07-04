# F56 Today Scan Usage Status

Status: completed

Purpose:

Make Today Scan explain whether scan candidates are usable for action or only for review when Daily Check blocks trade outputs.

## Scope

Allowed:

* Add backend-owned `usage_status` fields to Today Scan.
* Derive the status from existing `daily_check.json` and Today Scan buckets.
* Display the backend-owned status in Dashboard without recomputing blockers or candidates.
* Add focused backend and frontend structure tests.

Not allowed:

* Do not change strategy buckets, scores, candidates, or recommendation rules.
* Do not create candidates in frontend.
* Do not implement signal-alert acknowledgement or unblock behavior.
* Do not modify trades, holdings, cash, or formal personal records.

## Tasks

1. Status: done — Add failing service test for `usage_status` when Daily Check blocks trade outputs.
2. Status: done — Implement backend-owned Today Scan `usage_status`.
3. Status: done — Add frontend type / Dashboard rendering for usage status.
4. Status: done — Run focused verification, refresh Today Scan output if needed, update docs, and commit.

## Acceptance

* Today Scan includes `usage_status.can_use_trade_outputs`.
* When Daily Check blocks outputs, Today Scan includes a readable blocked headline and reason.
* Dashboard displays that backend-owned usage status.
* Frontend still does not recompute strategy, score, candidate buckets, blockers, or PM priority.

## Verification

* RED checks failed before implementation:
  * `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py::test_today_scan_report_includes_blocked_usage_status_from_daily_check -q`
  * `node --test frontend/tests/today-scan-dashboard.test.mjs`
* Focused backend tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py backend/tests/test_today_scan_api.py backend/tests/test_today_scan_cli.py -q` (`10 passed`).
* Focused frontend structure tests passed: `node --test frontend/tests/today-scan-dashboard.test.mjs frontend/tests/today-scan-api-contract.test.mjs` (`2 passed`).
* Frontend build passed: `npm run build`.
* Refreshed `backend/out/today_scan.json`; current `usage_status.status=blocked_by_daily_check` because Daily Check still blocks trade outputs via `signal_alerts`.
