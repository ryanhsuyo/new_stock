# F2.1 Official Fundamentals Source Expansion

Phase: Official fundamentals source expansion

Goal:

Expand official, low-frequency fundamentals inputs without turning fundamentals into a third strategy.

Scope:

* Keep F2 `BWIBBU_ALL.PEratio` -> `pe` behavior unchanged.
* Add TWSE listed-company monthly revenue report output from `opendata/t187ap05_L`.
* Preserve monthly revenue YoY and cumulative revenue YoY as neutral official reference fields.
* Keep TPEx / OTC official source as a documented blocker until a stable official endpoint is verified.

Do not:

* Fill ROE, EPS, FCF, interest coverage, or other financial-statement derived fields.
* Use TWSE listed-company data to fill OTC symbols.
* Promote fundamentals into a third recommendation strategy.

## Task F2.1-01 — Monthly Revenue Report Mapping

Status: done

Checklist:

* [x] Map official TWSE monthly revenue rows into neutral report fields.
* [x] Preserve `monthly_revenue_yoy_pct` and `cumulative_revenue_yoy_pct`.
* [x] Add skip reasons for missing YoY fields.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py -q
```

## Task F2.1-02 — CLI Report Output

Status: done

Checklist:

* [x] Add `--monthly-revenue-fixture` for network-free tests.
* [x] Add `--write-monthly-revenue-report` for report-only output.
* [x] Keep monthly revenue separate from priority CSV scoring fields.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q
```

## Source Decision

TWSE listed monthly revenue is verified as an official JSON OpenAPI source:

* `https://openapi.twse.com.tw/v1/opendata/t187ap05_L`
* Latest probe returned JSON rows with `公司代號`, `公司名稱`, `資料年月`, `營業收入-去年同月增減(%)`, and `累計營業收入-前期比較增減(%)`.
* Latest probe count: 1082 rows.

Final verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q
curl -s https://openapi.twse.com.tw/v1/opendata/t187ap05_L -o /private/tmp/twse_monthly_revenue.json
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -c "import json, pathlib; data=json.loads(pathlib.Path('/private/tmp/twse_monthly_revenue.json').read_text(encoding='utf-8')); print(type(data).__name__, len(data)); first=data[0] if data else {}; print([k for k in ['公司代號','公司名稱','資料年月','營業收入-去年同月增減(%)','累計營業收入-前期比較增減(%)'] if k in first])"
```

Latest result:

* Focused fundamentals flow tests passed, 45 tests.
* Official TWSE monthly revenue endpoint returned JSON `list` with 1082 rows and required fields.

TPEx / OTC monthly revenue source is not completed in this slice. Do not fill OTC fields from TWSE data.
