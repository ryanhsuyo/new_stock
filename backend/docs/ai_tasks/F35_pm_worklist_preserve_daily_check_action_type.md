# F35 PM Worklist Preserve Daily Check Action Type

## Goal

Make PM Worklist preserve backend-owned `daily_check.json.top_actions[*].action_type` for generic Daily Check actions.

## Scope

Allowed:

* Preserve `action_type` from Daily Check when mapping non-duplicated generic actions.
* Keep existing special handling for `data_freshness`.
* Add focused PM Worklist tests.
* Update docs and loop state.

Not allowed:

* Rebuild PM grouping logic in frontend.
* Change Daily Check top action generation.
* Change strategy scores, recommendation buckets, trades, holdings, cash, or formal records.

## Checklist

* [x] Add failing PM Worklist test for preserving Daily Check `action_type`.
* [x] Use Daily Check-provided `action_type` with fallback `daily_check`.
* [x] Run focused PM Worklist tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `git diff --check`

## Result

Completed. PM Worklist generic Daily Check items now preserve backend-owned `action_type` values.
