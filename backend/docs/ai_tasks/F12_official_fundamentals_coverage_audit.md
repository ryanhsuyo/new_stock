# F12 Official Fundamentals Coverage Audit

Status: completed

## Goal

Build a small read-only coverage audit for official fundamentals report-only CSV files.

The audit should help answer:

* Which priority / focus stocks already have official reference rows?
* Which official report-only files are missing or stale?
* Which fields are still blocked because they require true financial statement formulas or unavailable sources?

Hard rules:

* Read-only audit only.
* Do not write `fundamentals.csv`, `fundamentals.json`, or priority CSV.
* Do not fill `dividend_years`, growth CAGR, ROE, FCF, or any derived formal field.
* Do not turn fundamentals into a third strategy.
* Keep routers thin; service/script may read generated report CSVs.

## Tasks

1. Source / file contract decision
   - Status: done
   - Define which official report CSVs participate in the audit and which key columns count as present.
   - Participating reports:
     - `twse_bwibbu`: `pe`
     - `twse_monthly_revenue`: monthly / cumulative revenue YoY
     - `tpex_daily_pe`: PE / dividend yield / PB
     - `profitability`: operating / pre-tax / after-tax margin
     - `balance_sheet`: assets / liabilities / equity
     - `income_statement`: revenue / operating profit / net income / EPS
     - `dividend`: cash / stock dividend

2. Service test
   - Status: done
   - Use fixed CSV fixtures to verify coverage status per code and per report.

3. Service implementation
   - Status: done
   - Build a read-only summary from priority fill CSV plus official report-only CSVs.

4. CLI or API exposure
   - Status: done
   - Added CLI report-only JSON output first. API wrapper is deferred to F13.

5. Verification
   - Status: done
   - Run focused backend tests.

## Output

`backend/out/official_fundamentals_coverage_audit.json`

CLI:

```bash
cd backend
python3 scripts/update_fundamentals_official.py --write-coverage-audit
```

Optional test / custom directory:

```bash
python3 scripts/update_fundamentals_official.py --official-report-dir /path/to/reports --write-coverage-audit /path/to/audit.json
```

The audit reports:

* priority target count
* official report file status
* per-code report availability
* present key fields
* missing files / missing rows / empty values
* formal fields still blocked

## Verification

Passed:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q
```

## Acceptance

* The audit can show official report availability for priority stocks.
* Missing files / missing rows produce clear reasons.
* No strategy score or required fundamentals field is modified.
