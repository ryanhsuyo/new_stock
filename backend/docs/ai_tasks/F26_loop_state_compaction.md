# F26 Loop State Compaction

## Goal

Keep heartbeat execution reliable by shrinking `loop_state.md` back into a concise state file.

## Scope

Allowed:

* Archive long verification history into `backend/docs/ai_tasks/archive/`.
* Keep only current execution state, recent phases, and recent verification pointers in `loop_state.md`.
* Update `ai_execution_plan.md` to point idle heartbeats back to the F21 operating contract.

Not allowed:

* Change strategy logic.
* Change generated `backend/out/*` files manually.
* Change trades, holdings, cash, or formal trading records.

## Checklist

* [x] Confirm `loop_state.md` is approaching the 200-line AI-facing limit.
* [x] Create an archive summary for old verification history.
* [x] Rewrite `loop_state.md` as a compact current-state file.
* [x] Update execution plan wording from F25 to F26.
* [x] Run docs sanity checks.

## Verification

* `wc -l backend/docs/ai_tasks/loop_state.md backend/docs/ai_tasks/F26_loop_state_compaction.md backend/docs/ai_tasks/archive/loop_state_verification_archive_2026-07-01.md`
* `rg -n "F26|loop_state_verification_archive|Active phase: none|Phase ID: none|Last Verification" backend/docs/ai_tasks/loop_state.md backend/docs/ai_execution_plan.md backend/docs/ai_tasks/F26_loop_state_compaction.md`
* `git diff --check`

## Result

Completed. `loop_state.md` is compact again, and older verification history is available through the archive file.
