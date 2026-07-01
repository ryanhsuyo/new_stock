# F36 PM Worklist Daily Check Block Priority

## Goal

Make PM Worklist promote Daily Check `block` actions above warning-level maintenance actions so the Dashboard primary action points to the most urgent blocker first.

## Scope

Allowed:

* Adjust PM Worklist priority for generic Daily Check actions based on status severity.
* Preserve existing special handling for `data_freshness`.
* Add focused PM Worklist tests.
* Update docs and loop state.

Not allowed:

* Change Daily Check generation, strategy scoring, recommendation buckets, trades, holdings, cash, or formal records.
* Rebuild PM sorting in frontend.

## Checklist

* [x] Add failing PM Worklist test where Daily Check block outranks data freshness warning.
* [x] Adjust generic Daily Check priority for `status=block`.
* [x] Run focused PM Worklist and Daily Check tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `git diff --check`

## Result

Completed. PM Worklist now promotes generic Daily Check block actions above data freshness warnings.
