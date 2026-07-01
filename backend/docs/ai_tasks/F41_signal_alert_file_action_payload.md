# F41 Signal Alert File Action Payload

## Goal

Make Daily Check `signal_alerts` file actions fully actionable by including a safe copy command and expected outputs in the backend-owned payload.

## Scope

Allowed:

* Add `copy_command` for `backend/out/signal_alerts.json` file actions.
* Add `expected_outputs` so Dashboard / PM Worklist can show what file should be checked.
* Add focused backend tests.
* Update docs and loop state.

Not allowed:

* Change strategy scoring, recommendation buckets, trades, holdings, cash, or formal records.
* Apply or infer blocked fundamentals fields.
* Recompute PM priority in the frontend.

## Checklist

* [x] Add failing Daily Check test for signal alert file payload copy command / expected outputs.
* [x] Update `daily_check.py` signal alert payload.
* [x] Run focused Daily Check / PM Worklist / Update Workflow tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `git diff --check`

## Result

Completed. Daily Check `signal_alerts` file actions now include a safe copy command and expected outputs so Dashboard / PM Worklist can present the file-check step without guessing.
