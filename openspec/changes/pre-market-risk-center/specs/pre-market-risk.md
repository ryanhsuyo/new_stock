# Pre-market risk requirements

## Risk report

- 系統 MUST 回傳 level、score、headline、data_as_of、signals、guidance、official_sources 與 limitations。
- 每個市場 signal MUST 提供實際單日漲跌、狀態、points 與中文理由。
- 系統 MUST 清楚區分事件資料、行情資料與尚未自動串接的新聞來源。

## Safety

- stale 或不足資料 MUST 回傳 `unknown`，不得回傳 `normal`。
- `defensive` / `extreme` MUST 建議暫停一般新倉，但不得自動產生交易或修改策略輸出。
- 前端 MUST 顯示這是風險提示而非崩盤預測。

## Compatibility

- 不修改 TW / US OHLCV、交易、持倉與推薦輸出。
- API 計算失敗不得阻塞既有 Dashboard 核心資料載入。
