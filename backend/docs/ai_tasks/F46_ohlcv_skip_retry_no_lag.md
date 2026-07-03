# F46 OHLCV Skip Retry No-Lag Guard

Status: completed

Purpose:

Prevent tracked stocks from remaining partially stale when the official TWSE
monthly OHLCV endpoint temporarily returns empty / non-OK data for a small
subset of symbols during the same daily update run.

## Problem

`daily_update.py` can complete successfully while `data_freshness` still reports
partial stale rows. The observed case was `2412` and `2882`: the first pass
skipped them, but the official `STOCK_DAY` endpoint later returned the current
month data. Treating this as an acceptable `action_required` state leaves the
product in a data-lag condition.

## Scope

Allowed:

* Add a same-run retry pass for codes skipped by `backfill_ohlcv_twse.py`.
* Keep retries low-frequency and visible in CLI logs.
* Preserve SKIP output for codes that still have no official data after retry.
* Add focused tests.

Not allowed:

* Do not modify trading records, holdings, or cash.
* Do not change strategy rules or recommendation buckets.
* Do not manually edit generated `backend/out/*`.
* Do not fake OHLCV rows.

## Tasks

1. Add failing test for skipped-code same-run retry.
   Status: done

2. Implement `retry_skipped_stocks` and wire it into the backfill CLI before
   writing `ohlcv.csv`.
   Status: done

3. Run focused backfill tests.
   Status: done

4. Run daily update and verify `2412` / `2882` reach the latest data date.
   Status: done

5. Run full backend tests and update loop state.
   Status: done

## Acceptance

* `backend/tests/test_backfill_tpex.py::test_retry_skipped_stocks_recovers_transient_empty_twse`
  passes.
* `daily_update.py --months 1` no longer leaves `2412` / `2882` stale when the
  official endpoint has current-month rows.
* `backend/out/daily_check.json` / update workflow no longer reports partial
  stale tracked stocks for recoverable skipped codes.
