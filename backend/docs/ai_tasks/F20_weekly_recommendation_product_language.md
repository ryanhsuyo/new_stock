# F20 Weekly Recommendation Product Language

Status: done

## Goal

Make the recommendation page read like a stable weekly product surface rather
than a daily trading feed.

## Context

The system has daily scan outputs, but the formal recommendation list should
not imply that every daily scan is a new official buy list. The UI should make
the distinction clear:

* Daily Scan / Today Scan = daily candidates, risks, and alerts.
* Weekly Recommendation = main weekly list for planned observation and action.

## Guardrails

* Do not change strategy logic.
* Do not change recommendation buckets.
* Do not add a third strategy.
* Keep this as product wording and navigation clarity.

## Changes

1. Renamed the main tab from `推薦清單` to `本週推薦`.
2. Added an explanatory note on the recommendation page.
3. Added a frontend structure test to prevent wording regression.

## Verification

* `node --test frontend/tests/weekly-recommendation-language.test.mjs`

## Result

The product now separates weekly official recommendations from daily scan
signals in the UI language.
