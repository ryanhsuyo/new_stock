# Tasks

## Phase 1 — US research and watchlists

- [x] 定義 US 單股 analysis response 的必要欄位與 nullable 欄位。
- [x] 新增 US 單股 analysis endpoint（支援 `as_of`）。
- [x] 新增 US 研究頁 / K 線並使用 USD 顯示（共用 lightweight-charts，不偽造 TW StockAnalysis）。
- [x] 美股市場總覽、觀察訊號、trend-follow candidates/excluded、W-bottom patterns 全部加入本機研究頁連結。
- [x] watchlist item 增加 region，相容既有缺 region=TW 的資料。
- [x] 補 API、service、storage 測試，並完成前端 build / 瀏覽器流程驗收。

## Phase 2 — US update workflow

- [x] 新增 US update status store 與 background update lock。
- [x] 新增 US update-now endpoint，執行既有 US backfill。
- [x] 前端提供更新按鈕、3 秒 polling、完成後刷新 US 資料。
- [x] 驗證 US 更新命令只執行 US backfill，不寫入 TW OHLCV / status。

## Phase 3 — Trades, portfolio and stats

- [ ] 確認 US fee / tax / fractional-share 規則；未確認前不得實作正式損益。
- [ ] trades / watchlists 契約加入 region、currency、market 並保持舊資料相容。
- [ ] 投組與統計依 region / currency 分開聚合。
- [ ] 共用交易、持倉、統計 UI 加 market context。

## Phase 4 — US validation

- [x] 新增 region-aware US validation response 契約（逐筆等權口徑，與 TW 投組口徑誠實分開）。
- [x] 接 us_trend_follow / us_wbottom_target 回放服務與日期區間。
- [x] 共用驗收入口與日期操作，顯示 USD、US market 與 US 策略限制。
- [x] fixture smoke test、完整 pytest、frontend build 與桌面瀏覽器流程驗收。
- [ ] 補手機寬度 RWD 瀏覽器驗收。
