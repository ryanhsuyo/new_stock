# F43.4 Block And Schedule Actionability

## Goal

Make block alerts and schedule / update freshness actionable without automatically installing or running local schedulers.

## Verify First

Before editing behavior:

* Inspect Daily Check / PM Worklist block actions.
* Inspect update workflow / schedule health services and tests.
* Verify whether schedule absence or stale update logs are visible in current output.

## Scope

Allowed:

* Add read-only status or PM action text for missing schedule / stale update log.
* Add safe copy commands or file/action payloads for block alert inspection.
* Update docs to clarify manual schedule installation remains a user action.

Not allowed:

* Auto-install launchd, cron, or other scheduled tasks.
* Run long data updates automatically from this phase.
* Modify trades, holdings, cash, or formal records.

## Checklist

* [x] Verify whether block alerts lack a safe inspection / recovery path.
* [x] Verify whether schedule absence or stale update logs are invisible.
* [x] Add focused tests for whichever issue exists.
* [x] Implement minimal backend-owned actionability improvements.
* [x] Run focused tests.
* [x] Update F43 umbrella, `ai_execution_plan.md`, and `loop_state.md` to move to F43.5 or stop with a clear reason.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `git diff --check`

## Result

Status: completed.

Block alert file actions already had safe inspection payloads. Update Workflow now also exposes schedule health status / overdue / message in read-only `checks`, without installing or running local schedulers.
