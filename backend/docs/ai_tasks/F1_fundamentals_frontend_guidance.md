# F1 Fundamentals Frontend Guidance

Phase: Dashboard fundamentals workflow guidance

Goal:

Make Dashboard / Daily Check clearly show the backend-provided fundamentals workflow state, especially `fill_priority_csv`, without recreating strategy or fundamental rules in frontend.

Required reading:

* `backend/docs/current_rules.md`
* `backend/docs/signal_rules.md`
* `backend/docs/homepage_pm_roadmap.md`
* `backend/docs/ai_execution_plan.md`
* `backend/docs/ai_tasks/loop_state.md`

Allowed files:

* `frontend/**`
* `backend/docs/ai_tasks/**`
* `backend/docs/ai_execution_plan.md`
* `backend/docs/ai_tasks/loop_state.md`

Do not:

* Recompute strategies, scores, recommendation buckets, PM priority, or fundamental rules in frontend.
* Add a third strategy.
* Fabricate EPS, ROE, PE, or other fundamentals values.
* Modify trades, holdings, cash, backend strategy logic, or generated `backend/out/*` by hand.

## Task F1-01 — Inspect Existing Contracts

Status: done

Checklist:

* [x] Read `frontend/src/components/DailyCheckBox.tsx`.
* [x] Read `frontend/src/pages/Dashboard.tsx` fundamentals focus handling.
* [x] Read `frontend/src/types/index.ts` Daily Check and fundamentals types.
* [x] Record whether type fields already cover `workflow_stage`, `workflow_headline`, `workflow_primary_action`, and `workflow_checklist`.

Result:

`FundamentalsStatus.workflow_summary` was typed, but `DailyCheckAction.details` did not type the workflow details forwarded by Daily Check.

Verification:

```bash
rg -n "DailyCheckReport|workflow_stage|workflow_checklist|FundamentalsWorkflow" frontend/src
```

## Task F1-02 — Type The Daily Check Fundamentals Workflow Details

Status: done

Checklist:

* [x] Add or refine frontend types for Daily Check action details.
* [x] Include `workflow_stage`, `workflow_headline`, `workflow_primary_action`, and `workflow_checklist`.
* [x] Keep details optional and backward compatible.

Verification:

```bash
cd frontend
npm run build
```

## Task F1-03 — Render Fundamentals Workflow In Daily Check

Status: done

Checklist:

* [x] In `DailyCheckBox`, detect fundamentals top actions by `action.key === "fundamentals"`.
* [x] Show workflow headline and stage when provided.
* [x] Show the workflow primary action label/path as backend-provided guidance.
* [x] Show checklist steps with done / todo / blocked state.
* [x] Provide a clear path to copy the file path or action payload text.
* [x] Do not add frontend-derived strategy or scoring logic.

Verification:

```bash
cd frontend
npm run build
node --test tests/*.test.mjs
```

## Task F1-04 — Reconcile Docs And Stop

Status: done

Checklist:

* [x] Mark completed tasks in this file.
* [x] Update `backend/docs/ai_execution_plan.md` active phase to none.
* [x] Update `backend/docs/ai_tasks/loop_state.md` with F1 completion, verification, and next stop reason.
* [x] Report changed files, commands, verification, and remaining risk.

Verification:

```bash
git status --short
```
