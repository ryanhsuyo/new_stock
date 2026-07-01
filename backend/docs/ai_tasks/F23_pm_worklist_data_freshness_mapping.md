# F23 PM Worklist Data Freshness Mapping

Status: completed

Purpose:

Make PM Worklist treat Daily Check `data_freshness` actions as product-health / data freshness work, not generic Daily Check follow-up.

## Context

F22 added a first-class Daily Check `data_freshness` top action when some universe rows are stale. PM Worklist currently preserves the action payload, but maps unknown Daily Check actions as `action_type="daily_check"` with lower priority.

## Scope

Map Daily Check `data_freshness` into a PM Worklist item with:

* key: `data_freshness`
* action type: `data_freshness`
* source: `daily_check`
* higher priority than fundamentals follow-up
* focus codes from `action_payload.preview_items` when present
* same command payload from Daily Check

## Guardrails

* Do not change strategy rules.
* Do not trigger data updates.
* Do not modify generated out files by hand.
* Do not touch trades, holdings, cash, or personal records.

## Acceptance

* PM Worklist tests cover the mapping and priority.
* Focused PM Worklist tests pass.
* Phase docs and loop state are updated.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q` passed, 11 tests.
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py -q` passed, 33 tests.
