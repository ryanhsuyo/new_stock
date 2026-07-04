# F57 Update Scheduler Health Readiness

Status: completed

Purpose:

Make daily update health more product-readable by exposing a backend-owned manual update fallback action alongside schedule health.

## Scope

Allowed:

* Add a read-only `manual_update_action` to data status / update workflow checks.
* Reuse the existing safe daily update command and expected outputs.
* Add focused backend tests.
* Update current rules and loop state.

Not allowed:

* Do not install launchd / cron.
* Do not edit files outside the repository.
* Do not run long network update jobs in this phase.
* Do not modify trades, holdings, cash, or formal personal records.

## Tasks

1. Status: done — Add failing data-status / update-workflow tests for manual update fallback action.
2. Status: done — Implement `manual_update_action` in backend service/model and workflow checks.
3. Status: done — Run focused verification.
4. Status: done — Complete docs, update loop state, and commit.

## Acceptance

* `GET /api/system/data-status` includes a backend-owned `manual_update_action`.
* The action contains a short command, full copy command, and expected outputs.
* Update Workflow `checks` preserves the same action for Dashboard / PM use.
* No scheduler installation or external update job is triggered.

## Verification

* RED check failed before implementation: `backend/tests/test_update_workflow.py::test_update_workflow_exposes_schedule_health_in_checks` was missing `checks.manual_update_action`.
* Focused backend tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_status.py backend/tests/test_update_workflow.py backend/tests/test_schedule_health.py -q` (`86 passed`).
* Frontend structure test passed: `node --test frontend/tests/daily-update-button.test.mjs` (`2 passed`).
* Frontend build passed: `npm run build`.
* Service output check passed with `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`: data-status and Update Workflow checks both expose `python3 scripts/daily_update.py --months 1`.
