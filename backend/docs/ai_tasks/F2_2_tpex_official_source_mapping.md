# F2.2 TPEx Official Source Mapping

Phase: TPEx official fundamentals source mapping

Goal:

Add a safe TPEx / OTC official reference feed without mixing TWSE listed-company data into OTC symbols.

Scope:

* Source: TPEx official page-backed JSON endpoint for daily PE / dividend / dividend yield / P/B.
* Endpoint: `https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate`
* Method: POST with `date`, `cate`, and `response=json`.
* Output mode: report-only CSV.

Do not:

* Write TPEx values into `fundamentals.csv` scoring fields in this slice.
* Fill ROE, EPS, FCF, interest coverage, or any derived 11-field value.
* Use TWSE listed data to fill OTC symbols.

## Task F2.2-01 — Source Verification

Status: done

Checklist:

* [x] Verify the TPEx official page exposes a JSON endpoint.
* [x] Verify returned fields include PE, dividend, dividend yield, P/B, and financial period.
* [x] Record that this is report-only until a merge rule is explicitly added.

Evidence:

* Official page: `https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-pe.html`
* Page action: `afterTrading/peQryDate`
* Latest probe returned `stat: ok`, `totalCount: 888`, fields `股票代號`, `公司名稱`, `本益比`, `每股股利`, `股利年度`, `殖利率(%)`, `股價淨值比`, `財報年/季`.

## Task F2.2-02 — Report Mapping

Status: done

Checklist:

* [x] Map TPEx official table rows into neutral report rows.
* [x] Normalize `N/A` PE as blank and add `tpex_pe_missing_or_na`.
* [x] Keep dividend/PB fields as reference fields.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py -q
```

## Task F2.2-03 — CLI Report Output

Status: done

Checklist:

* [x] Add `--tpex-daily-pe-fixture` for network-free tests.
* [x] Add `--write-tpex-daily-pe-report` for report-only CSV output.
* [x] Keep TPEx report separate from priority CSV scoring fields.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q
```

Final verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q
```

Latest result:

* Focused fundamentals flow tests passed, 47 tests.

## Remaining Blockers

* TPEx monthly revenue YoY source is not completed in this slice.
* Derived 11-field fundamentals still require an official financial statement source map and formulas.
