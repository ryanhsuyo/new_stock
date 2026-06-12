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

## 4. Active Phase

Phase ID: H2.5

Phase name: Homepage Contract & Documentation Reconciliation

Active phase file:

`backend/docs/ai_tasks/H2.5_homepage_contract.md`

## 5. Required Reading

Before changing code, read:

* `AGENTS.md`
* `CLAUDE.md`
* `backend/docs/current_rules.md`
* `backend/docs/signal_rules.md`
* `backend/docs/homepage_pm_roadmap.md`
* `backend/docs/ai_execution_plan.md`
* Active phase file listed above

Task files should reference these docs instead of copying their full content.

## 6. Stop Conditions

Stop and report if:

* All tasks in the active phase are complete.
* A product decision is required.
* A test/build failure occurs and the safe fix is unclear.
* Required local data, credentials, or permissions are missing.
* The change would require large refactoring outside the active phase.
* Git baseline is missing and it is unclear whether `backend/data/**` or generated files should be tracked.

## 7. Report Format

When stopping, report:

* Completed tasks
* Changed files
* Commands run
* Verification result
* Remaining tasks
* Suggested next prompt or commit message

## 8. File Size Rule

* Keep each AI-facing markdown file under 200 lines.
* If a file approaches 200 lines, split details into `backend/docs/ai_tasks/*.md`.
* Do not paste full long documents into AI task files; link to source docs instead.
* Prefer concise checklist items over long prose.
* Completed phase files may move to `backend/docs/ai_tasks/archive/`.
