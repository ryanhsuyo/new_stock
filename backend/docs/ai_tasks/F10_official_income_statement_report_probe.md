# F10 Official Income Statement Report Probe

Status: completed

## Goal

Build the next small report-only probe for official income statement sources.

Use only confirmed official OpenAPI endpoints:

* TWSE listed income statement: `/opendata/t187ap06_L_*`
* TPEx OTC income statement: `/mopsfin_t187ap06_O_*`

Hard rules:

* Report-only output only.
* Do not write `fundamentals.csv`, `fundamentals.json`, or priority CSV.
* Do not fill `eps_growth_5y_cagr`, `revenue_growth_5y_cagr`, `roe_5y_avg`, or any derived field yet.
* Do not fabricate missing industry variants, years, or OTC/listed data.
* Keep fundamentals as `steady_momentum` support data, not a third strategy.

## Tasks

1. Source shape decision
   - Status: done
   - Selected general-industry variants first:
     - TWSE `/opendata/t187ap06_L_ci`
     - TPEx `/mopsfin_t187ap06_O_ci`
   - Reason: both return stable JSON rows for code/name/year/quarter/revenue/operating profit/net income/EPS. Other industry variants need separate fixture tests before support.

2. Service/parser test
   - Status: done
   - Add fixed fixture tests for selected TWSE/TPEx income statement row normalization.

3. Service implementation
   - Status: done
   - Normalize code, name, year, quarter, revenue, operating profit, net income, EPS, source, and skip reason when official fields are present.

4. CLI/API report-only path
   - Status: done
   - Add a neutral CSV output only if field names are stable enough.

5. Verification
   - Status: done
   - Run focused backend tests.

## Output

`backend/out/official_fundamentals_income_statement.csv`

Fields:

* `code`
* `name`
* `year`
* `quarter`
* `revenue`
* `operating_profit`
* `net_income`
* `eps`
* `source`
* `skip_reason`

CLI:

```bash
cd backend
python3 scripts/update_fundamentals_official.py --write-income-statement-report
```

HTTP:

* `POST /api/system/fundamentals-official/reports`
* Includes `income_statement` in the default report-only set.

## Verification

Passed:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q
```

## Acceptance

* A generated neutral CSV can show listed + OTC income statement reference rows.
* Missing or malformed values produce skip reasons.
* No strategy score or required fundamentals field is modified.
