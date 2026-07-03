# F43.2 Old Wang Chip Freshness

## Goal

Make Old Wang chip-related reasons honest about the chip data date and stale state.

## Verify First

Before editing behavior:

* Locate where Old Wang reasons include foreign / investment trust / dealer chip numbers.
* Check how `backend/data/chips.json` exposes `data_as_of`.
* Compare current generated reasons against chip freshness metadata.

## Scope

Allowed:

* Add focused backend tests for chip `data_as_of` visibility or stale wording.
* Add backend-owned reason / risk note wording when chip data is old.
* Keep any chip freshness threshold conservative and documented.

Not allowed:

* Fetch or fabricate chip data.
* Change the Old Wang strategy definition without updating `current_rules.md`.
* Auto-refresh data or install schedules.

## Checklist

* [x] Verify whether current Old Wang reasons quote chip numbers without date context.
* [x] Add a focused failing test if the issue still exists.
* [x] Surface chip `data_as_of` and stale wording in backend-owned output where appropriate.
* [x] Run focused tests.
* [x] Update F43 umbrella, `ai_execution_plan.md`, and `loop_state.md` to move to F43.3 or stop with a clear reason.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_old_wang_v21.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `git diff --check`

## Result

Status: completed.

Old Wang chip reason text now includes `籌碼資料日 YYYY-MM-DD` when chip numbers are quoted, and marks data as stale when the chip date is at least 4 calendar days behind the signal date.
