# F37 Daily Check Blocker Trade Output Consistency

## Goal

Make `daily_check.json.can_use_trade_outputs` consistent with Daily Check blockers, including extra blocker actions such as signal alerts.

## Scope

Allowed:

* Treat `status=block` extra actions as blocking trade outputs in Daily Check summary.
* Preserve top action ordering and payloads.
* Add focused Daily Check / PM Worklist regression tests.
* Update docs and loop state.

Not allowed:

* Change strategy signals, recommendation buckets, or scoring.
* Modify trades, holdings, cash, or formal records.
* Hide generated reports or manually edit generated outputs.

## Checklist

* [x] Add failing Daily Check test for signal alert blockers setting `can_use_trade_outputs=false`.
* [x] Make Daily Check trade output flags consistent with blockers.
* [x] Regenerate `backend/out/daily_check.json` via script.
* [x] Run focused Daily Check and PM Worklist tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `git diff --check`

## Result

Completed. Daily Check now marks trade outputs unusable whenever report checks or extra actions include blockers.
