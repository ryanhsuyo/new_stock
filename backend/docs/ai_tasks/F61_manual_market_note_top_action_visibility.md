# F61 Manual Market Note Top Action Visibility

Status: completed

Purpose:

Keep stale manual market note guidance visible in Daily Check / PM flow even when signal alerts and other warnings are present, so the user can see that the market note is stale without expanding raw `summary.json`.

## Scope

Allowed:

* Adjust Daily Check top action selection so backend-owned `manual_market_note` guidance is not silently hidden by lower-value review-only warnings.
* Add focused backend tests.
* Update execution state docs.

Not allowed:

* Do not save or invent a market note.
* Do not clear `signal_alerts` or change `can_use_trade_outputs`.
* Do not modify generated `backend/out/*`, trades, holdings, or cash.
* Do not change strategy scoring or recommendation buckets.

## Tasks

1. Status: done — Added a failing `run_signals.write_daily_check_report()` regression test proving refreshed Daily Check snapshots must receive `summary.json` manual note state.
2. Status: done — Passed `signals_summary` through `run_signals.py`, `update_all_data.py`, and background `update_service.py` Daily Check refresh paths.
3. Status: done — Ran focused verification.
4. Status: done — Updated phase / loop state and committed changes.

## Acceptance

* A stale manual market note appears in `top_actions` even when `limit=3` and signal alerts, fundamentals, and Today Scan actions all exist.
* `signal_alerts` remains the first blocker and still blocks trade outputs.
* The lower-priority Today Scan review action can be omitted when needed to keep the manual note visible.

## Verification

* RED: `test_run_signals_daily_check_refresh_includes_manual_market_note_summary` failed because `signals_summary` was not passed.
* GREEN: the same test passed after wiring `summary.json` into Daily Check refresh wrappers.
* Focused suite passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_run_signals_cli.py backend/tests/test_schedule.py backend/tests/test_update_status.py -q` (`125 passed`).
