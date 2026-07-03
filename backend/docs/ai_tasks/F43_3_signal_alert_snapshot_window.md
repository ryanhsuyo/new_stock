# F43.3 Signal Alert Snapshot Window

## Goal

Make signal alert wording match the real comparison window from `previous_as_of` to `as_of`.

## Verify First

Before editing behavior:

* Inspect signal alert generation and Daily Check wording.
* Inspect current `backend/out/signal_alerts.json` shape, especially `previous_as_of`, `as_of`, and alert counts.
* Confirm whether any user-facing copy says or implies one-day / next-day changes.

## Scope

Allowed:

* Add focused backend tests for multi-day snapshot wording.
* Rename user-facing wording to "since previous snapshot" style when needed.
* Preserve existing alert payload shape unless a small additive field is required.

Not allowed:

* Rewrite snapshot storage.
* Inflate or suppress alerts without a tested rule change.
* Modify trades, holdings, cash, or formal records.

## Checklist

* [x] Verify current alert wording and snapshot date behavior.
* [x] Add focused failing tests if wording is misleading.
* [x] Implement backend-owned wording / metadata change.
* [x] Run focused tests.
* [x] Update F43 umbrella, `ai_execution_plan.md`, and `loop_state.md` to move to F43.4 or stop with a clear reason.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `git diff --check`

## Result

Status: planned.

Completed. Signal snapshot review and signal alerts now use "previous snapshot" wording and `snapshot_window_label` instead of implying one-day / next-day changes.
