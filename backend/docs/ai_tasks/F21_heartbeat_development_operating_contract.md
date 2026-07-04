# F21 Heartbeat Development Operating Contract

Status: completed

Purpose:

Make scheduled heartbeat development deterministic enough to keep improving the product without guessing, overreaching, or doing health-check-only loops.

## Problem

When `loop_state.md` has `Active phase: none`, the heartbeat can become too passive:

* It checks git status and output freshness.
* It sees no active phase.
* It reports that the system is healthy.
* It does not create a next small product phase, even when safe work exists.

This is correct but not useful enough for long-running product development.

## Operating Loop

Every heartbeat should follow this order:

1. Read `git status --short`.
2. Read `backend/docs/ai_execution_plan.md`, `backend/docs/ai_tasks/loop_state.md`, `backend/docs/current_rules.md`, `backend/out/daily_check.json`, `backend/out/today_scan.json`, `backend/out/summary.json`, and `backend/out/universe_report.csv` when present.
3. If an active phase exists, continue exactly one safe task from that phase.
4. If no active phase exists, pick the first safe item from the backlog below.
5. Create a new `backend/docs/ai_tasks/Fxx_*.md` phase file before changing code.
6. Keep the slice small, verify it, update docs, and commit if files changed.
7. Stop and notify when blocked by user decision, missing external data, unclear failing tests, or risk to trades / holdings / cash.

## Safe Backlog Order

When no active phase exists, choose the first clearly applicable item:

1. Product health and freshness: stale output detection, daily update status, update result clarity, stalled-run recovery, and safe refresh guidance.
2. Daily use path: reduce Dashboard / Daily Check / PM Worklist noise, make the primary action obvious, and preserve backend-provided action payloads.
3. Scanability: improve Today Scan / Universe Report readability, filters, strategy labels, score explanations, and daily-vs-weekly wording.
4. Two-strategy reliability: verify only `old_wang` and `steady_momentum` appear as recommendation strategies, while `core_technical_v2` remains internal.
5. Official fundamentals observability: improve report-only status, coverage, and PE-only apply guard visibility without applying blocked fields.
6. Documentation consistency: reconcile `ai_execution_plan.md`, `loop_state.md`, `current_rules.md`, and active phase files when they drift.

After F51, use `backend/docs/ai_tasks/F52_heartbeat_safe_backlog_plan.md` as the concrete phase queue for the next safe productization slice. Prefer F52 signal-alert review usability first, then F53 manual market note action clarity, then F54 fundamentals warning truthfulness, unless current output state makes an earlier health/freshness issue urgent.

## Slice Limits

Each heartbeat slice should normally stay within:

* One phase file.
* One focused feature or docs consistency improvement.
* Three to eight changed files unless tests or existing structure require more.
* Existing backend / frontend architecture.
* Focused tests or docs sanity checks.

Do not start broad refactors, new strategy work, new data providers, database work, or personal trading record edits from a heartbeat.

## Notify Policy

Notify the user when:

* Code or docs changed.
* Tests fail or verification is blocked.
* Data is stale, missing, or inconsistent enough to affect product use.
* A user decision is needed.

Stay quiet or send a short no-action heartbeat only when:

* The tree is clean.
* No active phase exists.
* The backlog has no safe applicable item.
* Outputs are healthy enough for the next user session.

## Guardrails

* Main recommendation strategies remain only `old_wang` and `steady_momentum`.
* `steady_momentum` is the external product name for Quality Momentum Lite.
* `core_technical_v2` remains an internal technical engine.
* Official fundamentals may apply only approved direct fields; currently PE is the only safe direct apply path.
* Do not infer or fill ROE, FCF, interest coverage, dividend years, five-year averages, or CAGR from incomplete report-only rows.
* Do not modify trades, holdings, cash, or formal personal records.

## Acceptance

F21 is complete when:

* This operating contract exists.
* `ai_execution_plan.md` points idle heartbeats here.
* `loop_state.md` records F21 as the latest completed phase.
* Docs sanity checks pass.
