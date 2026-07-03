# F47 Prevent Signal Test Output Pollution

Status: completed

Purpose:

Prevent backend tests from overwriting product-facing `backend/out/*` signal
outputs with fixed test dates such as `2026-01-28`.

## Problem

After a full backend test run, `backend/out/signal_alerts.json` and
`backend/out/signal_snapshot_review.json` can show a test fixture date even
though `summary.json` and the live daily update are current. This is not a
strategy issue; it is test output pollution.

## Scope

Allowed:

* Update tests to use `tmp_out` when calling `run_daily_signals`.
* Add focused assertions that signal snapshot / alert outputs remain isolated.
* Update execution docs.

Not allowed:

* Do not change strategy rules.
* Do not modify trades, holdings, or cash.
* Do not manually edit generated `backend/out/*` as the fix.

## Tasks

1. Identify the test that writes signal outputs to real `backend/out`.
   Status: done

2. Route the timeout signal test through the existing `tmp_out` fixture.
   Status: done

3. Run focused signal timeout / signal output tests and verify real
   `backend/out/signal_alerts.json` remains at the live date.
   Status: done

4. Run full backend tests and confirm product outputs are not polluted.
   Status: done

5. Update loop state and complete the phase.
   Status: done

## Acceptance

* Full backend tests pass.
* `backend/out/signal_alerts.json.as_of` remains aligned with
  `backend/out/summary.json.as_of` after tests.
* The worktree can be committed without generated output churn.
