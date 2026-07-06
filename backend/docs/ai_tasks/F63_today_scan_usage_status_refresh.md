# F63 Today Scan Usage Status Refresh

Status: completed

## Goal

Keep `today_scan.json.usage_status` aligned with the latest Daily Check after safe workflow state changes, especially after signal-alert acknowledgement.

## Guardrails

* Do not recompute strategies, scores, recommendation buckets, or candidates.
* Do not modify trades, holdings, cash, or formal personal records.
* Do not write fundamentals fields or loosen PE-only fundamentals apply rules.
* Only refresh backend-owned usage status metadata derived from current `daily_check.json`.

## Tasks

1. Status: done — Added a service-level helper that reloads existing `today_scan.json`, recomputes only `usage_status` from current Daily Check, and rewrites the current report/snapshot.
2. Status: done — Signal-alert acknowledgement refresh now updates Today Scan usage status after Daily Check refresh.
3. Status: done — Added focused tests proving candidates stay unchanged and usage status updates from blocked to ready.
4. Status: done — Updated execution docs / loop state and ran focused verification.

## Acceptance

* A reviewed signal-alert fingerprint can unblock Daily Check and Today Scan usage status without rebuilding candidate lists.
* Tests cover stale blocked `usage_status` being refreshed to ready when Daily Check is no longer blocked.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py::test_refresh_today_scan_usage_status_preserves_candidates -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py backend/tests/test_update_status.py::TestSignalAlertReviewsAPI -q`
