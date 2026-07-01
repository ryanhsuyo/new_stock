# F25 Today Focus Data Freshness

Status: completed

Purpose:

Show PM Worklist data freshness tasks in Today Focus so the first screen points to stale data before regular review work.

## Context

F22 created Daily Check `data_freshness` actions. F23 maps them into PM Worklist. F24 groups them with Dashboard data repair work. Today Focus can still skip the primary data freshness action because it ignores the primary action when deriving review focus codes.

## Scope

* When the PM Worklist primary action is `data_freshness`, create Today Focus items from its stale preview labels.
* Keep the action read-only: no frontend or backend should trigger the update automatically.
* Preserve existing portfolio risk and entry candidate behavior.

## Guardrails

* Do not change strategy logic.
* Do not run or trigger data updates.
* Do not modify trades, holdings, cash, or generated market data.

## Acceptance

* PM Worklist tests cover Today Focus data freshness.
* Focused PM Worklist tests pass.
* Phase docs and loop state are updated.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q` passed, 12 tests.
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py -q` passed, 34 tests.
