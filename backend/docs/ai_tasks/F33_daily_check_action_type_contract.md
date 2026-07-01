# F33 Daily Check Action Type Contract

## Goal

Make `daily_check.json.top_actions` easier for product UI and PM workflows to consume by giving every top action a stable backend-owned `action_type`.

## Scope

Allowed:

* Add `action_type` to Daily Check generated top actions.
* Preserve existing `key`, `status`, `title`, `message`, `details`, and `action_payload`.
* Add focused backend tests.
* Update docs and loop state.

Not allowed:

* Change strategy scores, recommendation buckets, or trading decisions.
* Modify trades, holdings, cash, or formal trading records.
* Manually edit generated `backend/out/*` files.
* Move Daily Check grouping logic into frontend.

## Checklist

* [x] Add failing backend test for stable `top_actions[*].action_type`.
* [x] Add minimal Daily Check action-type mapping.
* [x] Run focused Daily Check tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `git diff --check`

## Result

Completed. Daily Check top actions now include stable backend-owned `action_type` values for product UI and PM workflows.
