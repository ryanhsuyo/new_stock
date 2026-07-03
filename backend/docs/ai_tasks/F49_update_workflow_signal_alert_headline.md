# F49 Update Workflow Signal Alert Headline

Status: completed

Purpose:

Make Update Workflow explain signal-alert blockers directly in the headline,
so the Dashboard first screen shows why trade outputs are blocked without
requiring the user to expand the action payload.

## Problem

When `Daily Check` blocks trade outputs due to `signal_alerts`, Update Workflow
currently uses a generic headline:

`Daily Check 判斷交易輸出不可使用，需先處理阻塞。`

The `next_action` has the detailed alert count and preview, but the headline is
the first thing users see. It should summarize the blocker count.

## Scope

Allowed:

* Change Update Workflow headline wording for Daily Check blockers.
* Prefer backend-provided `signal_alerts` details (`alert_count`,
  `block_count`, `warn_count`, `info_count`).
* Add focused tests.

Not allowed:

* Do not change signal generation or strategy semantics.
* Do not modify trades, holdings, or cash.
* Do not make router compute this.

## Tasks

1. Add failing test for signal-alert blocker headline.
   Status: done

2. Implement backend-owned headline helper.
   Status: done

3. Run focused Update Workflow tests.
   Status: done

4. Run full backend tests and complete phase.
   Status: done

## Acceptance

* Update Workflow headline for signal-alert blockers includes alert count and
  block / warn counts.
* Existing next action payload and preview items are preserved.
* Full backend tests pass.
