# F38 Update Workflow File Blocker Copy Command

## Goal

Make Update Workflow produce a safe executable copy command when the Daily Check blocker action is a file reference.

## Scope

Allowed:

* Convert Daily Check `action_payload.kind="file"` blocker actions into `cat <file_path>` copy commands.
* Preserve original action payload for frontend display.
* Add focused Update Workflow tests.
* Update docs and loop state.

Not allowed:

* Change Daily Check generation, strategy scoring, recommendation buckets, trades, holdings, cash, or formal records.
* Execute file actions automatically.

## Checklist

* [x] Add failing Update Workflow test for file blocker copy command.
* [x] Convert file blocker to safe `cat` command.
* [x] Run focused Update Workflow / PM Worklist / Daily Check tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `git diff --check`

## Result

Completed. Update Workflow now converts Daily Check file blockers into safe executable `cat <file_path>` copy commands while preserving the original payload.
