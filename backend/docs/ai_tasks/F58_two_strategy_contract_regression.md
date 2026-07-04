# F58 Two-Strategy Contract Regression

Status: completed

Purpose:

Protect the product contract that only `old_wang` and `steady_momentum` are visible recommendation strategies, while `core_technical_v2` remains an internal signal engine.

## Scope

Allowed:

* Add focused backend / frontend contract tests.
* Remove internal `core` from user-facing aligned strategy lists if exposed.
* Update phase state and current rules if needed.

Not allowed:

* Do not add, rename, or rebalance strategies.
* Do not change recommendation bucket logic except to enforce the two-strategy contract.
* Do not modify trades, holdings, cash, or generated output files manually.

## Tasks

1. Status: done — Add RED regression tests for two-strategy aligned output.
2. Status: done — Implement the smallest contract fix.
3. Status: done — Run focused backend / frontend strategy contract verification.
4. Status: done — Complete docs, update loop state, and commit if changed.

## Acceptance

* Recommendation buckets remain exactly `old_wang` and `steady_momentum`.
* `aligned_strategies` exposed by signals contain only product strategy IDs.
* `core_technical_v2` remains documented as internal and may appear only in rules metadata / internal descriptions.

## Verification

* RED check failed before implementation: `backend/tests/test_strategy_alignment.py` exposed `core` in `aligned_strategies`.
* Backend strategy alignment tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_strategy_alignment.py -q` (`4 passed`).
* Backend signals contract tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput::test_summary_has_strategy_catalog_and_buckets backend/tests/test_signals_api.py::TestSignalsOutput::test_signal_snapshot_outputs_are_written -q` (`2 passed`).
* Frontend two-strategy UI test passed: `node --test frontend/tests/two-strategy-ui.test.mjs` (`4 passed`).
