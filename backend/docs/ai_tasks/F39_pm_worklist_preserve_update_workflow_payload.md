# F39 PM Worklist Preserve Update Workflow Payload

## Goal

Make PM Worklist preserve the backend-owned `Update Workflow.next_action.action_payload` so Dashboard primary actions keep file / API context and previews.

## Scope

Allowed:

* Merge Update Workflow `next_action.action_payload` into the PM Worklist update-workflow item.
* Preserve safe `copy_command`, `command`, `current_step`, and `expected_outputs`.
* Add focused PM Worklist tests.
* Update docs and loop state.

Not allowed:

* Rebuild frontend action parsing.
* Change Update Workflow decision logic.
* Change strategy scoring, recommendation buckets, trades, holdings, cash, or formal records.

## Checklist

* [x] Add failing PM Worklist test for preserving update workflow file payload.
* [x] Merge payload context into PM Worklist update workflow item.
* [x] Run focused PM Worklist / Update Workflow tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `git diff --check`

## Result

Completed. PM Worklist update-workflow items now preserve Update Workflow action payload context while adding copy command metadata.
