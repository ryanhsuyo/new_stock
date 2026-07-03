# F50 Signal Alerts Review Contract

Status: completed

Purpose:

Make Daily Check signal-alert blockers easier to review by exposing a structured preview contract for the top blocking / warning alerts. This improves the daily PM path without changing strategy logic or auto-clearing blockers.

## Scope

Allowed:

* Add structured `preview_alerts` items to the existing `signal_alerts` Daily Check action payload.
* Preserve existing `preview_items` text for backward compatibility.
* Keep alert ordering block -> warn -> info.
* Add focused backend tests.

Not allowed:

* Do not modify strategies, scores, recommendation buckets, trades, holdings, cash, or formal trading records.
* Do not auto-resolve or acknowledge signal-alert blockers.
* Do not move signal-alert review logic into the frontend.

## Tasks

1. Status: done — Add a failing Daily Check test for structured `preview_alerts`.
2. Status: done — Implement the minimal `preview_alerts` contract in `backend/scripts/daily_check.py`.
3. Status: done — Run focused Daily Check tests.
4. Status: done — Update phase status and `loop_state.md`.

## Verification

* RED: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_signal_alert_payload_includes_structured_preview_alerts -q` failed with `KeyError: 'preview_alerts'`.
* GREEN: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_signal_alert_payload_includes_structured_preview_alerts -q` passed.
* Focused: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q` passed (`25 passed`).
* Output refresh: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/daily_check.py --write-report` wrote `backend/out/daily_check.json`; exit code `1` reflects expected WARN/BLOCK daily status.

## Acceptance

* `top_actions[signal_alerts].action_payload.preview_alerts` exists.
* `preview_alerts` contains block-first structured items with `severity`, `code`, `name`, `title`, `action_label`, and `review_focus`.
* Existing `preview_items` remains unchanged.
* Focused Daily Check tests pass.
