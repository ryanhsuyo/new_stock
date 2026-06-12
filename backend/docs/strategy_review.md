# 策略現況簡易報告

本報告依據目前程式碼與最近一次輸出檔檢視：

- 策略主體：`backend/app/services/signals_service.py`
- 型態辨識：`backend/app/services/pattern_service.py`
- 單檔分析：`backend/app/services/analysis_service.py`
- 規則文件：`backend/docs/signal_rules.md`
- 最近輸出：`backend/out/summary.json`、`backend/out/universe_report.csv`

基準輸出日期：`2026-05-06`

## 1. 目前策略已做到什麼

目前策略核心已具備第一版可用的技術分析資料流：

1. 可從 `leaders.json` 股票宇宙讀取標的。
2. 可讀取 `ohlcv.csv`，依每檔股票計算日線訊號。
3. 可輸出 `summary.json` 與 `universe_report.csv`。
4. 每檔股票都有可讀理由：`reasons`、`risk_note`、`no_buy_reason`。
5. 內部已使用 7 種狀態：
   - `entry_confirmed`
   - `ready_to_enter`
   - `watchlist`
   - `hold`
   - `take_profit_warning`
   - `exit_warning`
   - `invalidated`
6. 對外仍保留舊 API 契約：
   - `BUY`
   - `SELL`
   - `HOLD`
   - `DATA_MISSING`

目前規則重點如下：

- 長線趨勢：以 MA60 判斷。
- 短線趨勢：以 MA20 與 MA60 多頭排列、收盤是否站上 MA20 判斷。
- 支撐壓力：用最近 20 根 K 棒不含今日的低點與高點。
- Breakout：收盤站上壓力，且量能大於等於 1.5 倍均量。
- Breakdown：收盤跌破支撐 2% 以上。
- Pullback 準備入場：長線多頭，且接近 MA20 或支撐區。
- 型態辨識：已支援 W 底、M 頂、頭肩底。
- 分數：由 50 分起算，依趨勢、支撐壓力、突破跌破、量能、RSI、型態加減分。

## 2. 最近一次輸出觀察

最近一次 `universe_report.csv` 共 57 檔：

| 類別 | 數量 |
| --- | ---: |
| BUY | 12 |
| SELL | 32 |
| HOLD | 13 |
| DATA_MISSING | 0 |

內部訊號分布：

| 內部訊號 | 數量 |
| --- | ---: |
| ready_to_enter | 12 |
| watchlist | 12 |
| hold | 1 |
| take_profit_warning | 12 |
| exit_warning | 20 |
| entry_confirmed | 0 |
| invalidated | 0 |

重點解讀：

- 目前沒有任何 `entry_confirmed`，代表策略很少觸發「放量突破壓力」。
- 12 檔 BUY 全部是 `ready_to_enter`，也就是「準備入場 / 回測型」，不是突破確認型。
- SELL 很多來自兩類：
  - `exit_warning`：長線跌破 MA60。
  - `take_profit_warning`：RSI 過熱或接近壓力。
- 資料完整度目前很好，57 檔都有足夠資料。

目前 BUY 清單特徵：

- 多數是長線偏多且靠近 MA20 或支撐。
- 其中不少量能偏低，例如 0.5x 到 0.8x。
- 有些標的同時帶有 M 頂形成中，但仍被列為 BUY，例如 `3231`、`2412`、`2603`、`1301`、`1303`、`00919`。

## 3. 目前策略的主要缺口

### 3.1 分數與訊號語意會打架

目前有些高分股票不是 BUY，例如：

- `3017` 奇鋐：HOLD / watchlist / score 100
- `3324` 雙鴻：HOLD / watchlist / score 100
- `3653` 健策：HOLD / watchlist / score 100
- `6274` 台燿：HOLD / watchlist / score 100
- `3711` 日月光投控：SELL / take_profit_warning / score 95

這代表分數目前比較像「趨勢與型態強度」，但外部訊號比較像「當下是否適合進場」。兩者沒有錯，但如果不拆開，使用者會疑惑：為什麼 100 分卻不是買入？

建議改成兩種分數：

- `trend_score`：趨勢與結構分數。
- `entry_score`：當下進場品質分數。

這樣高趨勢但太乖離的股票可以呈現為：

- 趨勢強：高分
- 進場品質：低分
- 結論：等回測，不追高

### 3.2 BUY 條件太容易被 pullback 觸發

目前 `ready_to_enter` 條件是：

- 長線多頭
- 接近 MA20 或接近支撐

這會導致只要長線多頭且位置還可以，就可能被列入 BUY。它尚未嚴格要求：

- 短線重新轉強
- 收盤站回 MA5 / MA20
- 量能回溫
- 最近幾日止跌
- 型態不是明顯偏空

建議把 `ready_to_enter` 拆成兩層：

- `watchlist_pullback`：回測中，尚未止跌。
- `ready_to_enter`：回測後已出現止跌或轉強條件。

### 3.3 `entry_confirmed` 過少

目前突破確認要求：

- 收盤高於近 20 日壓力。
- 量能大於等於 1.5 倍。

這個條件可能太硬，導致最近輸出完全沒有 `entry_confirmed`。可以保留嚴格突破，但增加次級分類：

- `breakout_attempt`：收盤接近或小幅突破壓力，但量能不足。
- `breakout_confirmed`：突破且量能足。

如此可讓 summary 解釋「不是沒有突破，而是突破品質不足」。

### 3.4 型態辨識有過度寬鬆風險

目前型態偵測已有 W 底、M 頂、頭肩底，但從輸出看：

- `w_bottom confirmed` 很多。
- 有些頸線看起來與現價距離很遠，例如某些 W 底頸線很低，但仍被當作 confirmed 加分。
- 部分 BUY 同時出現 `m_top forming`，語意上容易混淆。

建議型態加上「新鮮度」與「距離限制」：

- confirmed 後超過 N 日，降權或標記為 stale。
- 頸線距現價過遠時，不再作為當下入場加分。
- M 頂 forming 若存在，至少應提高風險或降低 `ready_to_enter` 優先級。

### 3.5 出場策略仍偏粗

目前出場多依賴：

- 長線跌破 MA60
- 跌破支撐
- RSI 過熱
- 接近壓力

對持股來說還缺：

- 成本價與現價的風險報酬判斷。
- 停利分批規則。
- 追蹤停損，例如跌破 MA20、前低、或高點回落固定百分比。
- 獲利股與虧損股應使用不同語氣與條件。

## 4. 建議的策略更新進化

### 第一階段：修正訊號可解釋性

優先建議：

1. 拆分 `score`：
   - `trend_score`
   - `entry_score`
   - `risk_score`
2. 在 summary 增加：
   - 高分但不買的原因統計。
   - `ready_to_enter` 與 `entry_confirmed` 的差異說明。
   - 進場品質不足原因，例如量能不足、乖離過大、短線未站回 MA20。
3. 將 `BUY` 對外語意細分：
   - `ready_to_enter` 仍可映射 BUY，但推薦文案應明確說「準備觀察入場」，不是直接買。
   - `entry_confirmed` 才是「突破確認」。

### 第二階段：讓 ready_to_enter 更嚴格

建議新增條件：

- 收盤站上 MA5 或連續 2 日不破前低。
- RSI 在 40 到 70，超過 70 降權。
- 量能不能過低，或至少需比前一日回升。
- 若 `m_top forming`，不得直接列為 ready_to_enter，除非重新突破前高。

### 第三階段：改善型態品質

建議新增：

- `pattern_age_days`
- `neckline_distance_pct`
- `pattern_quality`
- `pattern_invalid_price`

型態不要只回傳 `forming / confirmed / failed`，還要能說明：

- 型態是否太舊。
- 現價距離頸線是否太遠。
- 失效價在哪裡。
- 是否仍值得作為當下訊號依據。

### 第四階段：加入市場環境濾網

台股很多個股會受大盤與族群影響，目前策略只看單檔。建議加入輕量濾網：

- 加權指數或櫃買指數是否站上 MA20 / MA60。
- 族群是否同步偏多。
- 若大盤長線偏空，個股 BUY 降權。

這不需要大型模型，只要多一份 index OHLCV 就能做第一版。

### 第五階段：持股策略獨立化

建議讓持股分析不要完全共用候選股邏輯。持股應更重視：

- 成本。
- 報酬率。
- 停利區。
- 停損區。
- 是否續抱。
- 是否減碼。

候選股看「能不能進」，持股看「要不要續抱」，兩者目標不同。

## 5. 建議優先實作順序

短期最值得做：

1. 拆分分數，避免 100 分卻 HOLD / SELL 的語意衝突。
2. 嚴格化 `ready_to_enter`，增加止跌與量能條件。
3. 型態加入新鮮度與頸線距離，避免舊型態持續加分。
4. summary 增加「不買原因分類」的標準化欄位，不要全部依自然語句統計。

中期再做：

1. 大盤濾網。
2. 族群濾網。
3. 持股出場規則獨立化。
4. 回測或至少固定測資情境比較。

暫時不建議做：

- 複雜預測模型。
- 過多技術指標。
- 新資料庫。
- 大型架構重構。

## 6. 總結

目前策略已經具備「可跑通、可解釋、有報表」的第一版基礎。最大問題不是功能不足，而是策略語意還需要整理：

- `score` 應拆成趨勢強度與進場品質。
- `ready_to_enter` 應比現在更嚴格。
- 型態訊號應加入新鮮度與距離，避免舊型態過度影響分數。
- summary 應用標準化原因碼，讓「為什麼不買」可以被穩定統計。

## 7. 已完成的第一波進化

已加入第一版專業濾網：

- `market_regime` / `market_filter`：以 `0050` 代理大盤環境。
- `relative_strength_score`：比較個股 60 / 120 日報酬是否強於 `0050`。
- `stage`：以 MA60 與其斜率建立簡化 Weinstein Stage Analysis。
- `trend_score` / `entry_score` / `risk_score`：拆分趨勢、進場品質、風險水位。
- `stop_price` / `target_price` / `reward_risk_ratio`：加入風險報酬判斷。
- `ready_to_enter`：加入止跌、量能、RSI、風險報酬與 M 頂風險濾網。

最近一次更新後，BUY 從 12 檔降為 1 檔，代表系統已從「長線多頭且接近 MA20」改為更接近「大盤允許、位置合理、風險報酬可接受、沒有明顯偏空型態」才列為準備入場。

後續最值得做的是「型態新鮮度」與「族群相對強度」，讓 W 底 / M 頂不會因過舊或族群轉弱而持續影響分數。
