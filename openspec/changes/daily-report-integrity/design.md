# Design

## Smaller viable route

沿用現有 JSON storage、trades router、React 交易紀錄頁與 Markdown artifact。交易修正採單筆 `PATCH`，只允許既有交易欄位並沿用原本驗證；前端使用既有表單元件，不建立第二套資料管理系統。

## Report boundaries

- `strategy_trade_report_tw_2026-05-01.md`: 每日台股行動報告。
- `strategy_trade_audit_tw_2026-05-01.md`: 歷史交易、合規與資料品質稽核。
- `strategy_trade_report_us_2026-05-01.md`: 美股每日行動與回放摘要；主要清單和型態詳表不得重複列同一已突破標的。

排程產生 TW 時同步更新 daily 與 audit；Monitor 的台股主卡仍只開 daily，避免增加第四張常駐卡片。Audit 由 daily 明示 artifact 名稱，後續可在 New Stock 交易頁提供入口。

## Integrity rules

- 交易價落在同日 OHLCV 區間外時，台股實績只稱「暫估」。
- 系統不得依 OHLCV 自動覆寫使用者輸入。
- 修正後重新產生報告，稽核結果必須由同一套檢查邏輯重算。
- 美股 fixed-as-of 測試需在加入未來 K 棒後仍產生相同的當日決策。
- Today Scan 的 usage status 必須在最新 Daily Check 寫入後刷新，不可保留上一批次 blocker。
- 台股 `universe_report.csv` 只要含多個資料日，日報就保留資料警示但不輸出今日進場／降風險清單。
- 台股報告排程延後至 15:40，避開 15:30 日常更新同時搶鎖，也提高 TPEX 當日資料完整率。
- 自動 OHLCV 檢查是範圍合理性檢查，不等同人工對帳。
