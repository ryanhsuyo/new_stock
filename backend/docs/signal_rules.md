
---

## 2. `backend/docs/signal_rules.md`

```md id="x9mccj"
# signal_rules.md — 股票分析與訊號規則

本文件定義本專案的技術分析核心規則、訊號分類方式、輸出欄位規格與持股分析原則。
本系統重點是提供「可解釋的技術位置與訊號」，不是提供保證式投資建議。

---

## 1) 功能定位原則

本專案不直接輸出以下語氣：
- 強烈推薦買入
- 一定會漲
- 建議重壓
- 保證獲利
- 精準預測高點 / 低點

本專案允許輸出以下狀態：
- `watchlist`：觀察中
- `ready_to_enter`：準備入場
- `entry_confirmed`：入場確認
- `hold`：可續抱
- `take_profit_warning`：停利注意
- `exit_warning`：出場警示
- `invalidated`：型態失效

系統應描述「目前技術位置與條件是否成立」，而不是保證未來走勢。

### 1.1 收盤復盤 / 隔日計畫定位

本系統的內部技術訊號與老王 tag 預設使用「已收盤日線」產生復盤結論與隔日交易計畫。

- 收盤後：可正式產生 `summary.json`、候選股報告、進場區間、停損與停利計畫
- 盤中：僅適合作為監控，例如觀察 5 / 10 / 20 / 60 均線、缺口、爆大量低點是否被破壞
- 未收盤 K 線不可視為正式訊號，不應把盤中突破/跌破直接寫成 `entry_confirmed` 或 `exit_warning`
- 盤中模式使用 `intraday_monitor`，與日線復盤訊號分開；只回傳 `healthy` / `caution` / `risk` / `data_missing`
- `intraday_monitor.invalidates_daily_plan=true` 代表盤中已破壞隔日計畫的關鍵觀察點，但正式 `summary.json` / `universe_report.csv` 仍等收盤後重算

---

## 2) 技術分析核心規則

### 2.1 先看長線，再看短線
- 先用長週期判斷主趨勢，再用短週期找進出場
- 長線可使用月線 / 週線
- 短線可使用日線
- 若長線偏空，短線做多訊號必須降權或不觸發

### 2.2 長線保護短線
- 若長線偏多，短線突破可提高分數
- 若長線偏空，短線多頭型態僅列入觀察，不直接列入入場確認
- 不允許短線單一訊號直接推翻長線主要方向

### 2.3 每檔股票都要先建立四條線
分析時至少要建立以下四種概念：
- `support_line`
- `resistance_line`
- `uptrend_line`
- `downtrend_line`

### 2.4 支撐與壓力第一版用簡單規則
第一版先用區間高低點：
- 壓力線 = 最近 N 根 K 棒的高點區間
- 支撐線 = 最近 N 根 K 棒的低點區間

除非明確要求，不要一開始就做過度複雜的支撐壓力演算法。

### 2.5 支撐壓力採區間，不採單點
- 不要求價格精準碰到某一價位
- 可使用誤差範圍，例如 ±1% 或 ±2%
- 接近支撐 / 壓力應視為區間判斷，不是 `close == target_price`

### 2.6 趨勢線只連有效高低點
- 上升趨勢線：連接遞增低點
- 下降趨勢線：連接遞減高點
- 一旦被有效跌破或突破，該趨勢線視為失效
- 單股技術分析優先挑選至少三個有效觸點的趨勢線；觸點容許誤差為投影線價格的 ±2%
- 上升支撐若出現低於投影線 2% 以上的後續擺盪低點，或下降壓力出現高於投影線 2% 以上的後續擺盪高點，該多點候選失效
- API 僅回傳定義斜率的兩個端點 `p1/p2`，有效觸點數寫入 `note`；若沒有三點確認，保留最近兩個方向正確擺盪點的相容行為

---

## 3) 型態與狀態定義

### 3.1 可辨識型態至少包含
- `w_bottom`
- `m_top`
- `head_and_shoulders_bottom`
- `head_and_shoulders_top`

### 3.2 每個型態必須有狀態
- `forming`
- `confirmed`
- `failed`

禁止把 `forming` 當成 `confirmed`。

### 3.3 型態未完成時，只能列入觀察或準備入場
- 形成中的 `W` 底 / 頭肩底只能列入 `watchlist` 或 `ready_to_enter`
- 只有突破頸線 / 壓力且條件成立後，才可列為 `entry_confirmed`
- 形成中的頭肩頂只能提供風險警示，不得單獨強制 `SELL`；收盤跌破頸線後才是 `confirmed`

### 3.4 頭肩頂
- 使用三個擺盪高點，左右肩差距不超過 10%，頭部至少高於雙肩 3%
- 頸線取左肩至頭、頭至右肩兩段最低點的較低者，且需低於較低肩至少 3%
- `forming`：右肩完成但未跌破頸線，score `-10` 並提供 `risk_note`
- `confirmed`：收盤跌破或接近頸線 1% 範圍，score `-20` 並提供 `risk_note`
- `failed`：收盤高於頭部 3%，不保留空方扣分，改在 `reasons` 說明型態失效

---

## 4) breakout / breakdown 定義

- `breakout`：收盤價有效站上壓力線或頸線
- `breakdown`：收盤價有效跌破支撐線或頸線
- 若可行，可加入成交量條件確認突破有效性
- 若無量突破，不可直接視為高可信度訊號

### 4.1 Core 日線回測口徑

- 第一版只回測 `core`，不混入老王、基本面避雷、目前籌碼、目前基本面或人工盤後筆記
- D 日收盤後產生的訊號，最早只能以 D+1 實際下一根日 K 開盤價成交
- 訊號函式每次只能收到截至 D 日的個股與 0050 資料，且 `data_as_of` 必須等於 D 日
- 買進滑價向上、賣出滑價向下；手續費與賣出證交稅使用正式交易金額的相同四捨五入規則
- `entry_confirmed` / `ready_to_enter` 為進場狀態；`exit_warning` / `invalidated` 為全數出場狀態
- 預設期末未平倉只做淨變現估值，不偽造已實現交易；只有明確 `force_close` 才記錄強制平倉
- 回測至少輸出交易明細、總報酬、最大回撤、勝率、平均已實現損益與相同成本口徑的 buy-and-hold 基準

---

## 5) 訊號輸出規則

每檔股票分析結果至少包含：
- `stock_id`
- `name`
- `close`
- `long_trend`
- `short_trend`
- `market_regime`
- `relative_strength_score`
- `stage`
- `support_price`
- `resistance_price`
- `stop_price`
- `target_price`
- `reward_risk_ratio`
- `pattern_type`
- `pattern_status`
- `signal`
- `score`
- `trend_score`
- `entry_score`
- `risk_score`
- `reasons`
- `risk_notes`

### 5.1 `signal` 可用值
- `watchlist`
- `ready_to_enter`
- `entry_confirmed`
- `hold`
- `take_profit_warning`
- `exit_warning`
- `invalidated`

### 5.2 `reasons`
`reasons` 必須是可讀文字陣列，例如：
- 接近區間壓力
- `W` 底形成中
- 長線趨勢偏多
- 突破頸線但量能不足
- 跌破上升趨勢線

### 5.3 `risk_notes`
`risk_notes` 必須提供主要失敗條件，例如：
- 跌破前低則型態失效
- 長線仍未翻多
- 突破量能不足，可能是假突破

---

## 6) 分數設計原則

可以使用 `score` 進行排序，但分數只能作為輔助，不可取代 `reasons`。

範例加減分邏輯（可調整，但要能解釋）：
- 長線偏多 `+20`
- 短線偏多 `+10`
- 接近支撐且未破 `+15`
- `W` 底 `forming` `+10`
- 突破頸線 `+20`
- 成交量放大 `+10`
- 跌破上升趨勢線 `-20`
- 長線偏空 `-20`
- 頭肩頂 `forming` `-10`
- 頭肩頂 `confirmed` `-20`
- 資料不足 `-30`

若使用分數：
- 必須可追溯來源
- 不可只給總分，不給原因
- 不可出現高分但無解釋的結果

### 6.1 分數拆分
`score` 保留為舊 API 相容的總分，但報表與分析 endpoint 應同時輸出：

- `trend_score`：趨勢與結構強度，例如 MA60、Stage、相對強度
- `entry_score`：當下進場品質，例如 pullback 品質、突破、RSI、風險報酬
- `risk_score`：風險水位，例如大盤偏空、長線跌破、RSI 過熱、M 頂

若 `score` 高但 `entry_score` 低，應透過 `no_buy_reason` 解釋為「趨勢強，但當下不是好進場點」。

### 6.2 專業濾網第一版

第一版加入以下濾網：

- `market_regime`：以 `0050` 代理大盤環境，判斷 `bull` / `neutral` / `bear`
- `relative_strength_score`：股票 60 / 120 日報酬相對 `0050` 的強弱
- `stage`：以日線 MA60 斜率代理 Weinstein Stage Analysis
- `reward_risk_ratio`：以支撐 / 均線估算停損，以壓力區估算目標

`ready_to_enter` 不應只因長線多頭且接近 MA20 就觸發；還應檢查止跌、量能、RSI、風險報酬與偏空型態。

### 6.3 策略 tag：老王短波段與穩健動能

目前推薦策略固定兩種：

- `old_wang_market_chip_rotation`：老王短波段 / 大盤籌碼輪動
- `steady_momentum_v1`：Quality Momentum Lite

`core_technical_v2` 仍是內部技術訊號引擎，負責計算支撐壓力、長短線趨勢、breakout / breakdown、型態、相對強度、Stage、風險報酬與外部 `BUY` / `SELL` / `HOLD`；但它不再是獨立推薦桶。

老王策略只做推薦分流與觀察，不覆蓋原本主訊號。它的資料基礎只使用既有 `ohlcv.csv` 與 `leaders.json`，用以下代理條件模擬「大盤籌碼 + 族群輪動」：

- 大盤濾網不可為 `block`
- 老王大盤濾網優先使用 `TSE` / `OTC` 指數；兩者至少各有 10 根日線後，檢查是否守住 MA5 / MA10 與爆大量低點。若資料不足，暫以 `0050` 代理，避免新回補的短資料誤判為大盤轉弱。
- leaders 族群的 20 / 60 日平均報酬、站上 MA20 比例、突破比例形成 `sector_score`
- 個股需符合至少一種轉強型態：`leader_breakout`、`ma60_reclaim`、`low_hold_rebound`、`sector_catch_up`、`previous_high_breakout`、`volume_high_breakout`、`all_ma_reclaim`
- 不看單一 K 線：老王 tag 必須同時檢查量能或跳空支撐
- `old_wang_volume_signal`：`confirmed` 表示量能高於均量，`weak` 表示量能不足，不可只因單日紅 K 觸發
- `old_wang_ma_signal`：波段看 MA10；若收盤站上 MA5 且 MA5 > MA10，視為短波段沿 MA5 / MA10 往上
- `old_wang_support_state`：用 5 / 10 / 20 / 60 判斷支撐狀態；5 / 10 是短線止跌，20 / 60 是中長線結構
- `old_wang_previous_high_risk`：只有 5 / 10 / 20 / 60 全部跌破時，才視為前高 / 頭部型態風險升高
- `old_wang_previous_high_state`：`breakout` 表示突破前高壓力，`failed` 表示盤中過前高但收盤未站上，`near` 表示接近前高不追價
- `old_wang_volume_low_support`：最近 20 日爆量 K 中絕對成交量最大者，其低點若被守住，視為「爆大量低點支撐」
- `old_wang_volume_high_breakout`：收盤突破該爆量 K 高點，視為爆大量高點換手後續攻
- `old_wang_parabolic_ma10_hold`：短線噴出且遠離 MA20 時，不預設高點，改用 MA10 作為噴出行情的短線支撐觀察
- `old_wang_all_ma_reclaim`：收盤重新站回 MA5 / MA10 / MA20 / MA60，視為「四海遊龍」翻多觀察
- `old_wang_gap_type`：`gap_up` 視為可能的多方缺口支撐，`gap_down` 視為可能的空方缺口壓力
- 若向上跳空且缺口未回補，可增加多方支撐分數；若向下跳空形成壓力，老王 tag 降權或不成立
- 前高壓力突破後，不因漲幅大或 RSI 高就自動視為高點；需搭配 MA5 / MA10 / MA20 / MA60 是否跌破、爆大量低點、缺口與量能是否仍支持
- 若長線跌破 MA60、跌破支撐、Stage 4 或 RSI 過熱，tag 必須降權或不成立

推薦分流：

- `old_wang`：只列 `old_wang_market_chip_rotation` tag 成立
- `steady_momentum`：只列 `steady_momentum_v1` 成立

老王 tag 的設計重點是「不要因為大漲就自動賣出」，而是先看大盤是否允許、族群是否轉強、個股是否仍守住關鍵線；但若風險報酬不足或 RSI 過熱，仍只列觀察而不追價。

Quality Momentum Lite 滿分 100 分，定位為第二主策略，補老王短線高波動的盲點。此策略以價格動能為主，基本面只做低成本避雷，不追求完整價值投資資料庫：

- 中期趨勢 25 分：使用 `trend_score`、MA20 / MA60、Stage 與相對趨勢結構。
- 相對強度 20 分：使用 `relative_strength_score`，偏好 20 / 60 / 120 日表現優於大盤的標的。
- 進場位置 20 分：使用 `entry_score`，偏好回測守穩、突破品質佳、不是離均線過遠的標的。
- 風險報酬 15 分：`reward_risk_ratio >= 1.5` 才視為合理，低於 1.2 不給分。
- 過熱控制 10 分：RSI 過熱或收盤距 MA20 過遠時降分，避免追高。
- 基本面避雷 10 分：只使用低成本 guard 欄位（PE、營業利益率、負債權益比、營收/EPS 成長）。資料不足時給中性避雷分，不假裝基本面完整，也不要求 ROE、FCF、interest coverage 或 dividend years 才能運作。`fundamental_*` 是正式基本面輔助欄位，不是推薦策略。

穩健動能成立條件：

- `steady_momentum_score >= 75`
- 長線不可為 `down`
- `stage` 不可為 `stage_4`
- `market_filter` 不可為 `block`
- `risk_score <= 70`

基本面資料不再是獨立推薦策略；它只保留為補資料流程與穩健動能的避雷輔助。任何 `fundamental_*` 欄位都只能視為正式基本面輔助欄位，不可視為推薦桶。

### 6.4 每日作戰檢查表

每筆 signal 需輸出 `daily_checklist`，供前端以條件卡方式呈現，不再只靠一段文字或分數判斷。此欄位只結構化既有訊號，不覆蓋 `BUY` / `SELL` / `HOLD`。

每個 item 包含：

- `category`：`market` / `setup` / `risk` / `action`
- `label`：檢查項名稱，例如「大盤可做」、「個股型態」、「風險報酬」
- `status`：`pass` / `warn` / `fail` / `info`
- `detail`：人可讀說明，必須能解釋通過或未通過原因
- `key_price`：相關關鍵價，可為空字串

至少要包含大盤、個股條件、風險、明日動作四類；若有爆大量低點、跳空支撐或其他關鍵條件，可額外加入 `setup` 檢查項。

基本面避雷資料：

- 定位為穩健動能策略的基本面避雷與資料完整度參考，不是獨立推薦策略，也不參與短線 `BUY` / `SELL` 主訊號
- 資料來源預期為 `backend/data/fundamentals.json`
- 優先用 `python3 scripts/prepare_fundamentals_priority_import.py --write-template` 產生外部資料模板，再用 `/path/to/source.csv` dry-run；確認後以 `--apply` 寫出 `backend/out/fundamentals_priority_fill.csv`
- 正式合併需先跑 `python3 scripts/merge_priority_fundamentals.py` 預覽，再用 `--apply --confirm MERGE_PRIORITY_FUNDAMENTALS` 寫回 `fundamentals.csv` 並匯入 JSON
- 用 `python3 scripts/check_fundamentals.py` 檢查 leaders 股票中哪些缺整檔資料或缺必要欄位
- 沒有基本面資料時，必須回傳 `fundamental_data_ok=false` 與 `fundamental_data_missing_reason`，不可用技術指標假裝基本面分數；`fundamental_*` 是正式基本面輔助欄位
- Quality Momentum Lite 分數拆成以下正式輔助欄位：
  - `fundamental_quality_score`：以營業利益率為主，ROE / 現金流資料若存在才輔助加分
  - `fundamental_safety_score`：以負債權益比為主，利息保障倍數若存在才輔助加分
  - `fundamental_value_score`：以 PE 為主，FCF yield 若存在才輔助加分
  - `fundamental_growth_score`：以營收/EPS 成長為主，股利穩定性若存在才輔助加分
- `fundamental_flag=true` 代表「輕量基本面避雷通過」，不是短線買進訊號

盤中監控：

- `GET /api/stocks/{code}/intraday-monitor` 可傳入 `price`、`open_price`、`high`、`low`、`volume`
- 此 endpoint 只檢查盤中是否破壞 5 / 10 / 20 / 60、向上跳空支撐、爆大量低點
- 不寫入 `backend/out/*`，不產生正式 `BUY` / `SELL` / `HOLD`
- 開盤或盤中若跌破 5 / 10，只是 `caution`；只有 5 / 10 / 20 / 60 全破，或爆大量低點/向上缺口支撐被破壞，才標示 `risk`
- 收盤後仍須重新跑 `run_signals.py`，由日線收盤 K 產生正式訊號

盤後作戰輸出：

- `daily_brief.json` 需包含 `rotation_plan` 與 `tomorrow_tasks`
- `daily_brief.json` 需包含 `data_status`，讓前端或使用者先確認資料最新日、覆蓋率與 stale 狀態
- `data_status` 必須包含 `update_required`、`update_command`、`missing_stocks`；資料過期或有缺漏時，需直接告知日常更新指令
- `rotation_plan` 用於分桶：續抱、等回測、可進場、優先減碼、不追價
- `tomorrow_tasks` 用於逐檔隔日任務，必須保留每檔的 `bucket`、`trigger_action`、`watch_price`、`entry_plan`、`stop_plan`、`exit_plan`、`invalidation`
- `tomorrow_tasks` 不新增策略判斷，只整理既有 `daily_action`、`daily_key_price`、`entry_price_low/high`、`stop_price`、`target_price`、`price_plan_note` 與價格來源欄位
- 若沒有可進場區間，`entry_plan` 必須明確顯示不建議新進場，避免誤導追價
- `data_status.is_stale=true` 時，不應把該份作戰表當作當日最新決策依據，需先執行每日更新
- `signal_alerts.json` 由 `signal_snapshot_review.json` 衍生，只整理隔日 action 變化警示；`unchanged` 不列警示，且第一版不發 Slack / macOS / email 通知
- `rules_version` 與 `rules_metadata` 是輸出稽核欄位，需出現在 summary、daily brief、signal snapshot、snapshot review 與 signal alerts；第一版只記錄固定規則版本與主要參數，不提供動態改參數。
- `today_scan.json` / `scripts/today_scan.py` 只把既有 `universe_report.csv` 分桶成正式可小試、老王觀察、穩健動能與風險處理；它不是新策略，不得重算或覆蓋正式 `signal` / `daily_action`。`run_signals.py` 應在正式輸出更新後同步刷新此檔。

人工盤後筆記：

- `backend/data/market_notes.json` 可記錄人工貼上的盤後風控摘要，例如大盤廣度、台股 / 櫃買 MA5 / MA10 狀態、強勢股爆大量低點觀察
- 這份資料會被寫入 `summary.json.manual_market_note` 供 Dashboard 顯示
- 人工筆記只作為風控提示，不直接覆蓋正式 `BUY` / `SELL` / `HOLD`
- 若人工筆記指出「跌破 MA5」，系統語氣應偏向短線降水位；若進一步跌破 MA10 或爆大量低點，才轉為更高風險處理
- 強勢股若仍守住 MA10 與爆大量低點，不因單日長黑就自動判定行情結束

---

## 7) `summary.json` 規格

`summary.json` 至少要能回答：
- 本次分析股票總數
- 資料足夠的股票數
- 進入 `watchlist` / `ready_to_enter` / `entry_confirmed` 的數量
- 沒有買點的主因分布
- 若 `buy_list` 為空，為什麼為空
- `strategy_catalog`：列出目前策略 tag 名稱、角色與說明
- `recommendation_buckets`：分開列出 `old_wang`、`steady_momentum` 兩種方案推薦桶
- `calculation_timeout_seconds`：本次單檔計算 timeout 秒數
- `calculation_timeout_count`：本次逾時股票數量
- `calculation_timeout_codes`：本次逾時股票代碼；無逾時時為空陣列

---

## 8) `universe_report.csv` 規格

`universe_report.csv` 至少應包含：
- `code`
- `name`
- `data_ok`
- `signal`
- `score`
- `trend_score`
- `entry_score`
- `risk_score`
- `strategy_tags`
- `old_wang_flag`
- `old_wang_score`
- `old_wang_signal`
- `old_wang_reason`
- `old_wang_sector`
- `sector_score`
- `old_wang_volume_signal`
- `old_wang_gap_type`
- `old_wang_gap_support`
- `old_wang_gap_resistance`
- `old_wang_gap_note`
- `old_wang_ma_signal`
- `old_wang_volume_low_support`
- `old_wang_volume_low_price`
- `old_wang_support_state`
- `old_wang_ma_break_count`
- `old_wang_previous_high_risk`
- `old_wang_previous_high_state`
- `old_wang_previous_high_price`
- `old_wang_volume_high_breakout`
- `old_wang_volume_high_price`
- `old_wang_all_ma_reclaim`
- `old_wang_parabolic_ma10_hold`
- `fundamental_flag`
- `fundamental_tag`
- `fundamental_score`
- `fundamental_signal`
- `fundamental_reason`
- `fundamental_data_ok`
- `fundamental_data_missing_reason`
- `fundamental_quality_score`
- `fundamental_value_score`
- `fundamental_safety_score`
- `fundamental_growth_score`
- `market_regime`
- `relative_strength_score`
- `stage`
- `entry_price_low`
- `entry_price_high`
- `stop_price`
- `target_price`
- `reward_risk_ratio`
- `price_plan_note`
- `support_source`
- `resistance_source`
- `entry_source`
- `stop_source`
- `target_source`
- `pattern_type`
- `pattern_status`
- `calculation_status`：`ok` / `data_missing` / `timeout`
- `calculation_error`：正常時空白；資料不足或 timeout 時提供可讀原因
- `no_buy_reason`
- `risk_note`

重點：不只列出有買點的股票，也要能解釋大多數股票為何不符合條件。

價格來源欄位是 audit metadata：用來說明支撐、壓力、進場區、停損、目標價來自近期高低點、MA、壓力回測或區間延伸；不得把來源欄位當成新的買賣訊號。

單檔計算 timeout 規則：

- timeout 股票必須輸出 `data_ok=false`、`signal=DATA_MISSING`，不可產生買賣建議。
- `no_buy_reason` / `risk_note` / `reasons` 必須解釋計算未完成，不能誤標為一般無買點。
- timeout 後必須記錄股票代碼、秒數與 `compute_signal` 步驟，終止該 worker 後繼續下一檔。
- 非 timeout 的未知 worker 例外仍應中止批次並回報，不可轉成缺資料列。

---

## 9) API 設計原則

API 應回傳的是結構化分析結果，不是模糊敘述。

可接受的 API 類型：
- 取得單檔分析結果
- 取得觀察名單
- 取得準備入場名單
- 取得入場確認名單
- 取得持股檢查結果
- 取得 `summary` / `universe_report` 對應資料

不可接受：
- 只回傳一段無結構文字
- 只回傳推薦與否，不提供理由
- 只給分數，不給條件

---

## 10) 持股 / 出場分析原則

若分析持股，輸出應偏向：
- `hold`
- `take_profit_warning`
- `exit_warning`

可參考條件：
- 跌破支撐
- 跌破上升趨勢線
- 長線轉弱
- 爆量長黑
- 已偏離均線過遠，可提示停利注意

但仍應避免保證式語氣，不可直接宣稱一定該賣或一定會跌。

---

## 11) 先求可用，再求精準

第一版功能重點是「規則清楚、輸出可解釋、資料流跑通」。
若某個技術分析型態難以高精度實作，應先提供簡化但可維護的版本，
並清楚標示限制，不要為了追求完美而讓整體功能延後或過度複雜化。
