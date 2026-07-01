# F42 Daily Check Manual Note Awareness

## Goal

Make Daily Check surface stale manual market notes as a PM top action, using backend-owned API action payloads.

## Scope

Allowed:

* Read `summary.json.manual_market_note` into Daily Check.
* Add a warning top action when the manual note is stale or `update_required`.
* Use the existing safe `POST /api/stocks/market-notes` action payload.
* Add focused backend tests.
* Update docs and loop state.

Not allowed:

* Auto-write market notes.
* Change formal signals, strategy scoring, trades, holdings, cash, or formal records.
* Treat stale manual notes as a third strategy.

## Checklist

* [x] Add failing Daily Check test for stale manual note top action.
* [x] Load summary/manual note into Daily Check and add the action.
* [x] Run focused Daily Check / PM Worklist / Update Workflow tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `git diff --check`

## Result

Completed. Daily Check now reads `summary.json.manual_market_note` and surfaces stale / update-required notes as a safe API action.
