# F45 Signal Alert Action Hints

Status: completed

## Goal

Make each `signal_alerts.json` alert actionable by adding backend-owned action hints. This keeps Daily Check blockers meaningful without automatically clearing risk warnings.

## Guardrails

* Do not auto-acknowledge or clear signal alerts.
* Do not modify trades, holdings, cash, or decision journal.
* Do not change strategy scoring or recommendation buckets.
* Keep alerts read-only and derived from `signal_snapshot_review.json`.

## Tasks

1. Add focused tests for per-alert `action_label`, `next_action`, and `review_focus`.
2. Add outcome-specific action hints in `signal_alert_service`.
3. Regenerate signals so `backend/out/signal_alerts.json` includes the new fields.
4. Update `current_rules.md`, `ai_execution_plan.md`, and `loop_state.md`.

## Acceptance

* `risk_triggered` alerts say to review risk / invalidation first.
* `action_changed` alerts say to compare previous and current actions.
* `missing_current` alerts say to repair or inspect missing data.
* `risk_eased` alerts say to reassess without treating it as an automatic buy signal.
* Tests pass.
