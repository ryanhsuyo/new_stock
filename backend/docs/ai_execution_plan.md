# AI Execution Plan

## 1. Purpose

This file is the AI execution control file.

Agents must read this file first, then read the active phase file, then continue from the first task with `Status: todo`.

The goal is to keep AI work continuous, ordered, verifiable, and small enough to load reliably.

## 2. Global Rules

Hard rules:

* Do not introduce a database.
* Do not introduce new large frameworks.
* Do not perform large folder restructuring.
* Do not manually edit `backend/out/*` generated files.
* Do not modify trades, holdings, cash, or formal trading records unless explicitly requested.
* Do not commit unless explicitly requested.
* Routers must stay thin.
* Business logic belongs in `backend/app/services/**`.
* Storage logic belongs in `backend/app/storage/**`.
* Frontend must not recreate trading, signal, PM priority, or Today Focus strategy logic.
* If frontend changes are required, keep them minimal and make them consume backend contracts.
* Long commands should not be run directly in shell / python heredoc. Write long commands to files first, then execute with exec / node / shell to avoid truncation.

## 3. Continuous Execution Protocol

1. Read Required Reading.
2. Read the active phase file.
3. Find the first task with `Status: todo`.
4. Complete tasks in order.
5. After each task, update status in the phase file.
6. Run the relevant verification command.
7. Inspect changed files.
8. Continue until a Stop Condition is reached.

Do not stop after completing only one small item unless a Stop Condition applies.

## 4. Auto-Loop Protocol

When the active phase is complete, do not stop by default.

Instead:

1. Update the completed phase status and checklist.
2. Read `backend/docs/homepage_pm_roadmap.md`.
3. Read `backend/docs/ai_tasks/loop_state.md`.
4. Pick the next highest-priority incomplete roadmap item that can be done safely.
5. Create a compact phase file under `backend/docs/ai_tasks/`.
6. Update Active Phase in this file.
7. Update `backend/docs/ai_tasks/loop_state.md`.
8. Continue from the first `Status: todo` task in the new phase.

If there are multiple reasonable next phases, choose the one with the smallest safe product value slice.

Do not auto-loop into work that needs:

* A product decision.
* Large refactoring.
* New dependencies.
* Changes to trades, holdings, cash, or formal trading records.
* Manual editing of generated `backend/out/*` files.

## 5. Soft-Block Protocol

Some tasks are useful but not required to keep progress moving.

If an optional task is blocked, mark it `Status: soft-blocked`, record the reason, and continue to the next safe task or phase.

Soft-block examples:

* Browser screenshot access is denied.
* Mobile viewport control is unavailable.
* A visual check cannot run, but `npm run build` still passes.
* A documentation-only improvement has no live data to demonstrate.

Hard-stop examples:

* Backend tests fail and the safe fix is unclear.
* Frontend build fails.
* A task risks modifying trades, holdings, cash, or private data.
* A product decision is required.
* A required dependency, credential, or permission is missing for core functionality.

## 6. Active Phase

Phase ID: none

Phase name: none

Active phase file:

None. F33 is complete; idle heartbeats should follow `backend/docs/ai_tasks/F21_heartbeat_development_operating_contract.md` to choose the next safe productization slice.

## 7. Required Reading

Before changing code, read:

* `AGENTS.md`
* `CLAUDE.md`
* `backend/docs/current_rules.md`
* `backend/docs/signal_rules.md`
* `backend/docs/homepage_pm_roadmap.md`
* `backend/docs/ai_execution_plan.md`
* `backend/docs/ai_tasks/loop_state.md`
* `backend/docs/ai_tasks/F21_heartbeat_development_operating_contract.md` when there is no active phase
* Active phase file listed above

Task files should reference these docs instead of copying their full content.

## 8. Stop Conditions

Stop and report if:

* A product decision is required.
* A test/build failure occurs and the safe fix is unclear.
* Required local data, credentials, or permissions are missing.
* The change would require large refactoring outside the active phase.
* Git baseline is missing and it is unclear whether `backend/data/**` or generated files should be tracked.
* No safe next phase can be selected after reading the roadmap and loop state.

## 9. Report Format

When stopping, report:

* Completed tasks
* Changed files
* Commands run
* Verification result
* Remaining tasks
* Suggested next prompt or commit message

## 10. File Size Rule

* Keep each AI-facing markdown file under 200 lines.
* If a file approaches 200 lines, split details into `backend/docs/ai_tasks/*.md`.
* Do not paste full long documents into AI task files; link to source docs instead.
* Prefer concise checklist items over long prose.
* Completed phase files may move to `backend/docs/ai_tasks/archive/`.
