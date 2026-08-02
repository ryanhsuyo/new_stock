# Signal forward validation requirements

## ADDED Requirements

### Requirement: 前推驗收不得使用尚未產出的訊號
前推驗收 MUST 以 snapshot 的 `generated_at` 決定訊號何時可用，進場基準 MUST 是 `generated_at` 日期之後的第一個交易日開盤。MUST NOT 使用 `as_of` 當作可用時點。

#### Scenario: 快照延後產出
- **WHEN** 某快照 `as_of=2026-06-26` 但 `generated_at=2026-06-30T14:09`
- **THEN** 該日訊號的進場日 MUST 是 2026-06-30 之後的第一個交易日，而不是 2026-06-26 的次一交易日

#### Scenario: 快照當日產出
- **WHEN** 某快照 `as_of` 與 `generated_at` 同一天且在收盤後
- **THEN** 進場日 MUST 是該日之後的第一個交易日

### Requirement: 出場規則必須來自訊號本身
前推驗收 MUST 使用訊號當日記錄的 `daily_invalidation` 作為出場條件，收盤跌破後於次一交易日開盤出場。若該欄缺值，該筆 MUST 標記為 `no_stop_defined` 並排除於勝率統計之外，不得以任意補值取代。

#### Scenario: 觸發失效價
- **WHEN** 持有期間某日收盤低於訊號記錄的失效價
- **THEN** 出場價 MUST 為次一交易日開盤價，出場原因 MUST 記為 `stop`

#### Scenario: 資料末日仍未出場
- **WHEN** 到最後一筆 OHLCV 仍未觸發失效價
- **THEN** 該筆 MUST 標記為未平倉，並與已平倉筆數分開列示

### Requirement: 績效必須附同期市場對照
前推驗收輸出 MUST 同時包含同期市場中位報酬與基準指數報酬。MUST NOT 只呈現策略自身報酬。

#### Scenario: 跌段期間
- **WHEN** 策略平均報酬為 -6.94%，同期市場中位為 -12.09%
- **THEN** 輸出 MUST 同時呈現兩者，使「少跌」與「賺錢」不會被混淆

### Requirement: 樣本不足必須明示
當可用訊號筆數不足以支撐結論時，輸出 MUST 標示樣本數與「證據不足」，MUST NOT 省略該區塊或以空白呈現。

#### Scenario: 美股尚無快照
- **WHEN** 美股沒有任何 signal snapshot
- **THEN** 美股報告的證據狀態 MUST 顯示樣本數 0 與「尚無可驗收樣本」，MUST NOT 借用台股數字

### Requirement: 證據窗口固定為近一個月且必須標示實際涵蓋範圍
前推驗收的預設回看窗口 MUST 為最新資料日往前一個月。快照不連續時 MUST 印出該窗口內實際涵蓋的快照日數與訊號筆數，MUST NOT 假設窗口內每個交易日都有快照。

#### Scenario: 窗口內快照不連續
- **WHEN** 近一個月內只有 11 天有快照
- **THEN** 輸出 MUST 標明涵蓋 11 個快照日，而非以一個月的交易日數呈現

#### Scenario: 窗口內無任何訊號
- **WHEN** 近一個月內沒有任何 `BUY` 訊號
- **THEN** 證據狀態 MUST 印出樣本數 0 與「本窗口無訊號」，MUST NOT 自動延長窗口去湊樣本

### Requirement: 每日報告必須在結論前呈現證據狀態
台股與美股每日報告 MUST 在「今日結論」之前呈現策略當前證據狀態，內容包含前推樣本數、平均報酬、勝率、同期市場中位與最近一次護欄回放結果。台股三份 per-profile 報告 MUST 各自呈現該 profile 的證據狀態。

#### Scenario: 近期績效為負
- **WHEN** 最近一次前推驗收平均報酬為負
- **THEN** 報告 MUST 在進場候選之前印出該負值，MUST NOT 只放在附錄或省略

### Requirement: 快照必須保存風控狀態
`signal_snapshot` 的每個項目 MUST 保存 `old_wang_market_filter` 與 `old_wang_market_regime`，快照層級 MUST 保存當日盤前風險等級，使日後可重建當時的風控判斷。

#### Scenario: 重建歷史風控
- **WHEN** 對過去某日做前推驗收
- **THEN** 該日的風控狀態 MUST 可直接由快照讀出，MUST NOT 需要重算指數資料
