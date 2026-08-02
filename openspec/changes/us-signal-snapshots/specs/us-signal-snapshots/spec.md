# US signal snapshot requirements

## ADDED Requirements

### Requirement: 每日保存全部追蹤標的而非只保存可追蹤的
美股快照 MUST 保存當日全部追蹤標的，含觀望、不必看、已達目標與已失效各桶。MUST NOT 只保存「可紙上追蹤」桶。

#### Scenario: 濾網關閉的日子
- **WHEN** 當日大盤濾網關閉，可紙上追蹤 0 檔、觀望 12 檔
- **THEN** 快照 MUST 仍保存這 12 檔與各自的桶別，使日後能回答「當時看到什麼但沒動」

#### Scenario: 型態失效
- **WHEN** 某檔在當日轉為已失效
- **THEN** 快照 MUST 記錄該桶別，而不是把它從清單移除

### Requirement: 快照必須保存判斷當下的關鍵價位與濾網狀態
每個項目 MUST 保存 code、名稱、桶別、今日動作、策略、收盤、觸發價、失效價與觀察目標。快照層級 MUST 保存趨勢濾網 bias 與 active、W 底濾網 active、資料日與 `generated_at`。

#### Scenario: 事後重建當時判斷
- **WHEN** 對某個歷史日做前推驗收
- **THEN** 該日的觸發價、失效價與兩個濾網狀態 MUST 可直接由快照讀出，不需重算策略

### Requirement: 快照不得因為報告產生失敗而遺漏
產生美股報告時 MUST 一併寫出當日快照。若快照寫出失敗，該次執行 MUST NOT 被標記為成功。

#### Scenario: 排程檢查
- **WHEN** 美股報告產生成功但快照未寫出
- **THEN** 排程 MUST NOT 寫成功 marker

### Requirement: 同一資料日重複執行不得產生多份快照
以 `as_of` 命名，同一資料日重複執行 MUST 覆寫既有快照而不是新增一份。

#### Scenario: 當日重跑
- **WHEN** 同一個資料日執行兩次報告產生
- **THEN** `out/us_signal_snapshots/` MUST 只有一份該日快照
