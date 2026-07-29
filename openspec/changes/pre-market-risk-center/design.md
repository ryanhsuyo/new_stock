# Design

## Data flow

`ohlcv_us.csv` + `market_notes.json` → `pre_market_risk_service` → `GET /api/system/pre-market-risk` → Dashboard risk card.

Router 只轉 response model；行情與筆記分別沿用既有 storage。前端只呈現後端分級，不重算分數。

## Risk semantics

- `normal`: 目前可用證據未見明顯隔夜壓力。
- `watch`: 單一市場或事件訊號轉弱，降低追價與新倉規模。
- `defensive`: 多項風險共振，暫停一般新倉並降低曝險。
- `extreme`: 權值／科技市場出現極端同步壓力，維持防守並等待開盤波動收斂。
- `unknown`: 行情過期、缺少足夠基準或無法可靠判斷。

每項 signal 必須附 `reason` 與 points。分數只用於風險分級，不是推薦分數。

## Freshness guard

直接重用 US market freshness。資料 stale 時，`level=unknown`、`can_open_new_positions=false`、`max_exposure_pct=null`；避免舊資料給出虛假的安全感。

## News and events

第一版只把最近人工市場筆記視為已輸入的事件證據，並提供官方來源連結。自動抓取 MOPS／官方行事曆需另做可快取、可觀測且不依賴單一 DOM 的 collector。

### Official event summary slice

- 先以 `backend/data/official_market_events.json` 保存人工查證的官方排程，不新增資料庫或 collector。
- 每筆事件必須包含唯一 id、標題、台北時間、原始時區、重要程度、官方 URL 與 `verified_at`。
- API 只回傳未來 14 天與當日事件，依時間排序，並回報清單是否超過 7 天未查證。
- 事件清單只做風險提醒，不進入 `score`，也不改 `can_open_new_positions`；避免把「有事件」等同負面訊號。
- 前端顯示「今日／即將公布」、來源與查證狀態；不得宣稱已讀取新聞結果或預測市場反應。
