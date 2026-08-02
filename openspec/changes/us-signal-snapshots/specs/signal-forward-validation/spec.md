# Signal forward validation requirements

## ADDED Requirements

### Requirement: 美股只有可紙上追蹤桶計入績效
美股前推驗收 MUST 只把「可紙上追蹤」桶的標的計入績效統計。其餘桶 MUST 保存但不計分。

#### Scenario: 觀望桶不計分
- **WHEN** 某日可紙上追蹤 0 檔、觀望 6 檔
- **THEN** 該日對績效樣本的貢獻 MUST 為 0 筆，MUST NOT 拿觀望名單充樣本

#### Scenario: 濾網開啟時的新訊號
- **WHEN** 某日有 2 檔進入可紙上追蹤
- **THEN** 這 2 檔 MUST 計入樣本，進場基準為快照 `generated_at` 之後的第一個交易日開盤

### Requirement: 美股出場條件取型態失效價
美股前推驗收 MUST 以快照記錄的型態低作為失效條件，收盤跌破後於次一交易日開盤出場。MUST NOT 使用量幅目標作為停利出場，因為紙上追蹤沒有定義停利動作。

#### Scenario: 跌破型態低
- **WHEN** 持有期間收盤低於快照記錄的失效價
- **THEN** 出場價 MUST 為次一交易日開盤價

#### Scenario: 觸及量幅目標
- **WHEN** 持有期間收盤高於量幅目標但未跌破失效價
- **THEN** 該筆 MUST 仍視為持有中，MUST NOT 自動於目標價出場

### Requirement: 兩個市場的驗收結果不得混算
前推驗收 MUST 依市場分別統計。台股與美股的樣本 MUST NOT 合併計算平均或勝率。

#### Scenario: 美股尚無樣本
- **WHEN** 美股快照數為 0 而台股有 37 筆
- **THEN** 美股報告 MUST 顯示樣本 0，MUST NOT 顯示台股的 37 筆
