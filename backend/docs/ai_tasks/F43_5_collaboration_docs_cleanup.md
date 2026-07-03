# F43.5 Collaboration Docs Cleanup

## Goal

Remove stale collaboration guidance that can mislead heartbeats or future agents.

## Verify First

Before editing docs:

* Compare `AGENTS.md`, `CLAUDE.md`, `current_rules.md`, and active heartbeat contracts.
* Verify whether obsolete output files such as `buy_list.json` / `sell_list.json` are still documented as required.
* Verify whether frontend restrictions conflict with current user-approved productization work.

## Scope

Allowed:

* Update `AGENTS.md`, `CLAUDE.md`, and docs to match current two-strategy, productized-frontend reality.
* Keep restrictions that prevent frontend strategy recomputation.
* Remove obsolete references that no longer match generated outputs.

Not allowed:

* Weaken strategy guardrails.
* Add new frontend permissions beyond backend-contract display work.
* Change generated output schemas in this docs-only slice.

## Checklist

* [x] Verify stale docs references.
* [x] Update only misleading or obsolete guidance.
* [x] Run docs sanity checks.
* [x] Mark F43 umbrella complete if all child stages are done.
* [x] Return `ai_execution_plan.md` / `loop_state.md` to no active phase or select the next safe phase.

## Verification

* `rg -n "buy_list|sell_list|frontend|third strategy|第三" AGENTS.md CLAUDE.md backend/docs`
* `git diff --check`

## Result

Status: completed.

`AGENTS.md` and `CLAUDE.md` now list current generated outputs and allow frontend only for backend-contract product display work, while still forbidding frontend strategy / score / recommendation recomputation.
