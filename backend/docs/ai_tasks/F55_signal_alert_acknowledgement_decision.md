# F55 Signal Alerts Acknowledgement Decision

Status: completed

Purpose:

Plan a safe way to let the user mark signal-alert blockers as reviewed without modifying trades, holdings, cash, or silently unblocking trade outputs.

## Current Problem

`daily_check.json.can_use_trade_outputs=false` because `signal_alerts` has block-level alerts. F50-F52 made the review payload much easier to read, but the system still has no audited way to record that the user has reviewed the block alerts.

This phase is a decision/spec phase only. It does not implement acknowledgement writes or unblock logic.

## Options

### Option A — Keep No Acknowledgement

Summary:

Leave the current behavior unchanged. Block alerts remain blocking until the next signal run changes the alert set.

Pros:

* Safest implementation.
* No new state file or API.
* Impossible to accidentally unblock outputs.

Cons:

* PM workflow can stay blocked even after the user reviews the alerts.
* Trains the user to ignore a permanent block banner.
* Does not solve the product problem identified in the audit.

Decision:

Keep as fallback only. This is safe but not product-like enough for long-term use.

### Option B — Reuse `decision_journal.json`

Summary:

Record signal-alert review rows inside the existing decision journal.

Pros:

* Reuses an existing audit-like file.
* Already has API/service patterns for append-only user decisions.

Cons:

* Mixes "reviewed a blocker" with "made a stock decision".
* Some alert reviews may not be buy/sell/skip decisions.
* Higher risk of confusing PM review with trading intent.

Decision:

Do not use this as the default acknowledgement store. It may be linked later only when a review also creates a real decision-journal entry.

### Option C — Separate Signal Alert Review Ledger

Summary:

Create a dedicated review ledger, e.g. `backend/data/signal_alert_reviews.json`, for signal-alert acknowledgement state only.

Pros:

* Keeps alert review separate from trading records.
* Can store a stable alert fingerprint, comparison window, reviewer note, and reviewed timestamp.
* Allows Daily Check to decide whether the current block alerts have been reviewed without touching trades / holdings / cash.
* Easy to inspect, backup, and test with fixed fixtures.

Cons:

* Adds one small state file and service.
* Needs careful fingerprinting to avoid treating changed alerts as already reviewed.
* Requires explicit UI/API behavior before implementation.

Decision:

Recommended future path. Implement only after a small follow-up phase and explicit user approval.

## Recommended Future Design

If approved later, implement a separate signal alert review ledger with these rules:

* Storage: `backend/data/signal_alert_reviews.json`.
* Router: thin HTTP wrapper only, likely under `/api/system/signal-alerts/reviews`.
* Service: validates current `backend/out/signal_alerts.json`, computes alert fingerprints, and writes review records.
* No writes to `trades.json`, `positions.json`, `cash`, `fundamentals.json`, or official report outputs.
* A review record must include at least:
  * `as_of`
  * `previous_as_of`
  * `code`
  * `severity`
  * `title`
  * `alert_fingerprint`
  * `reviewed_at`
  * `review_status` (`reviewed` only for the first version)
  * optional `note`
* Fingerprint should be derived from stable alert fields, such as `previous_as_of`, `as_of`, `code`, `severity`, `title`, `previous_action`, `current_action`, `previous_key_price`, `previous_invalidation`, and `current_signal`.
* If any fingerprint-relevant field changes, the alert must require review again.

## Unblock Rule

The first safe unblock rule should be strict:

* `signal_alerts` may stop blocking only when every current `severity=block` alert in the latest `signal_alerts.json` has a matching reviewed ledger entry with the same `previous_as_of`, `as_of`, `code`, and `alert_fingerprint`.
* `severity=warn` and `severity=info` can remain visible as review items, but they should not alone force `can_use_trade_outputs=false`.
* A stale `daily_check.json`, stale `signal_alerts.json`, or changed alert fingerprint must invalidate the reviewed state.
* Manual review never changes BUY / SELL / HOLD, strategy score, recommendation bucket, holdings, cash, or trade records.

## Suggested Follow-Up Phase

F56 or later can implement the minimum safe slice if the user approves:

1. Add service tests using fixed `signal_alerts.json` and review-ledger fixtures.
2. Add a storage/service helper that reports reviewed vs unreviewed block alerts.
3. Add a read-only API/status field first; only then consider write API.
4. Keep Daily Check blocking behavior unchanged until write path and unblock tests exist.

## Acceptance

* The decision compares no acknowledgement, decision-journal reuse, and a separate review ledger.
* The recommended path does not modify trades, holdings, cash, or strategy outputs.
* The unblock rule is explicit and strict enough for a future implementation.
* No acknowledgement behavior is implemented in this phase.

## Verification

* Docs sanity check: this file contains no unresolved placeholder markers.
* Docs consistency check: `ai_execution_plan.md` and `loop_state.md` can return to no active phase after this decision.
