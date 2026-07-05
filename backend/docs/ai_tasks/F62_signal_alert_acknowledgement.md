# F62 Signal Alert Acknowledgement

Status: completed

Purpose:

Let the user mark the current `signal_alerts.json` set as reviewed so Daily Check can stop blocking trade-output usability for the exact same alert fingerprint, without changing strategies, scores, trades, holdings, or cash.

## Scope

Allowed:

* Add a small review ledger under `backend/data/signal_alert_reviews.json`.
* Add a service that fingerprints the current `backend/out/signal_alerts.json`.
* Add thin system API endpoints for reading review status and acknowledging the current alert set.
* Let Daily Check suppress the `signal_alerts` blocker only when the current fingerprint is reviewed.
* Add a PM Worklist / Dashboard action that calls the backend acknowledgement API.
* Add focused backend tests.

Not allowed:

* Do not auto-acknowledge alerts.
* Do not modify BUY / SELL / HOLD, strategy scores, recommendation buckets, trades, holdings, or cash.
* Do not treat a stale fingerprint as reviewed.
* Do not write generated `backend/out/*` files by hand.

## Tasks

1. Status: done — Added failing tests for reviewed current alerts, stale fingerprints, and system API read/write.
2. Status: done — Added `signal_alert_review_service` with stable fingerprinting and a dedicated review ledger.
3. Status: done — Added `GET /api/system/signal-alert-reviews` and `POST /api/system/signal-alert-reviews/current`.
4. Status: done — Wired Daily Check to suppress the blocker only when `reviewed=true` for the current fingerprint.
5. Status: done — Acknowledgement now refreshes Daily Check after writing the ledger.
6. Status: done — Added PM Worklist action wiring for `POST /api/system/signal-alert-reviews/current`.
7. Status: done — Ran focused and full verification.

## Acceptance

* Unreviewed block alerts still produce `can_use_trade_outputs=false`.
* Reviewing the current alert set records a fingerprint in `backend/data/signal_alert_reviews.json`.
* The same fingerprint is considered reviewed and no longer creates the signal-alert blocker.
* Any changed fingerprint requires review again.
* PM Worklist can trigger the backend acknowledgement API and refresh Dashboard state without frontend-side unblock logic.

## Verification

* RED: focused tests failed before implementation because the review service / Daily Check parameter / API did not exist.
* GREEN: focused tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_allows_trade_outputs_when_current_signal_alerts_are_reviewed backend/tests/test_daily_check.py::test_daily_check_keeps_signal_alert_block_when_review_fingerprint_is_stale backend/tests/test_update_status.py::TestSignalAlertReviewsAPI -q` (`4 passed`).
* Related suite passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_update_status.py backend/tests/test_update_workflow.py backend/tests/test_pm_worklist.py -q` (`122 passed`).
* Full backend suite passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` (`789 passed`).
* Frontend structure tests passed: `node --test frontend/tests/*.test.mjs` (`22 passed`).
* Frontend build passed: `npm run build`.
