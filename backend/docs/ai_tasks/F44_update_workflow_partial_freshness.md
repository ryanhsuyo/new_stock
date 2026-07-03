# F44 Update Workflow Partial Freshness Awareness

Status: completed

## Goal

Make Update Workflow surface partial stale universe data from Daily Check instead of reporting `ready` when only some tracked stocks lag the expected data date.

## Guardrails

* Do not change strategy rules or recommendation buckets.
* Do not run external data updates.
* Do not write `trades`, `holdings`, `cash`, or formal fundamentals fields.
* Keep router thin; this phase only changes service aggregation.

## Tasks

1. Add a focused backend test proving Daily Check `data_freshness` warning becomes Update Workflow `action_required`.
2. Preserve the Daily Check command payload, copy command, expected outputs, and stale item preview.
3. Expose partial stale / missing counts and stale items in Update Workflow `checks`.
4. Update current rules and loop state so future heartbeats do not regress this behavior.

## Acceptance

* `get_update_workflow_status()` returns `overall_status="action_required"` and `current_step="repair_partial_data_freshness"` when Daily Check reports stale tracked stocks.
* `can_use_trade_outputs` remains true when Daily Check allows trading outputs.
* `checks.partial_stale_count`, `checks.partial_missing_date_count`, and `checks.partial_data_freshness_items` are available for Dashboard / heartbeat observability.
* Focused update workflow tests pass.
