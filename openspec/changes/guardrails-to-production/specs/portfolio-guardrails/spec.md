# Portfolio guardrail requirements

## MODIFIED Requirements

### Requirement: 護欄作用範圍
護欄 MUST 同時作用於 evaluation 回放與 production 每日報告的進場清單。`daily_action` 為 `enter` / `probe` / `watch` 的候選，在盤前風險為 defensive / extreme、或超過每日新倉上限與曝險上限時，MUST NOT 列入「今日可能進場／觀察」。

先前「evaluation-only，不改 production 推薦旗標」的限制由本需求取代。護欄仍 MUST NOT 修改原始策略旗標、賣出與減碼訊號——擋單只影響進場清單的呈現，不改寫訊號本身。

#### Scenario: 盤前風險為防守
- **WHEN** 當日盤前風險等級為 defensive 且有 5 檔 `daily_action=enter` 候選
- **THEN** 「今日可能進場／觀察」MUST 為空，5 檔 MUST 全數出現在「今日不新增（風控擋下）」並各自帶原因

#### Scenario: 超過每日新倉上限
- **WHEN** 當日有 6 檔候選但每日新倉上限為 3 檔
- **THEN** 至多 3 檔進入進場清單，其餘 MUST 以 `daily_entry_limit` 原因列入風控擋下區塊

### Requirement: 盤前風險不得停在未知
production 盤前風險 MUST NOT 輸出 `unknown`。輸入不完整時 MUST 由當下可得資料推出等級，標示為 `degraded` 並列出缺少的輸入。推估等級 MUST NOT 比可得資料所支持的等級更寬鬆。

#### Scenario: 部分輸入缺漏
- **WHEN** SPY 與 QQQ 有資料但 TSM 缺漏
- **THEN** 系統 MUST 由 SPY / QQQ 推出等級、標示 `degraded`、列出缺少 TSM，且該等級 MUST NOT 寬鬆於僅由 SPY / QQQ 判斷所得的結果

#### Scenario: 全部輸入缺漏
- **WHEN** SPY / QQQ / TSM 皆無當日可用資料
- **THEN** 系統 MUST 取最保守等級並停止新倉，標示 `degraded` 與全部缺漏項，MUST NOT 預設為 normal

#### Scenario: 降級推估必須可見
- **WHEN** 當日風險等級為推估而得
- **THEN** 報告 MUST 在證據狀態區塊標明該日判斷為降級推估，MUST NOT 與正常計算的等級呈現得無法區分

### Requirement: 每個 profile 各自出報告且曝險上限不跨報告合併
台股每日報告 MUST 依 combined / old_wang / steady_momentum 各產生一份 artifact，每份只套用該 profile 的上限。每份報告 MUST 印出「上限僅在本報告內有效，同時依多份報告進場會放大實際曝險」的警告。

#### Scenario: 三份報告各自擋單
- **WHEN** 某檔在 old_wang profile 通過上限但在 steady_momentum profile 超過每日新倉上限
- **THEN** 該檔 MUST 出現在 old_wang 報告的進場清單、同時出現在 steady_momentum 報告的風控擋下區塊

#### Scenario: 排程部分失敗
- **WHEN** 三份報告中有一份產生失敗
- **THEN** 成功標記 MUST 只記錄實際成功的 artifact，MUST NOT 因其餘兩份成功而標記整體成功

### Requirement: 被略過的候選必須可稽核
被護欄略過的候選 MUST 記錄 code、訊號日、規則代碼與原因，並在每日報告中可見。報告的分桶筆數 MUST 加總回候選總數。

#### Scenario: 分桶加總
- **WHEN** 當日共 8 檔候選，3 檔進入進場清單、5 檔被風控擋下
- **THEN** 報告 MUST 印出合計 8 檔，使任何被靜默丟棄的候選都能被發現

#### Scenario: 擋單原因可讀
- **WHEN** 某檔因 `pre_market_gate` 被擋
- **THEN** 報告 MUST 以人看得懂的文字說明（例如「盤前風險 防守，停止新倉」），MUST NOT 只印 reason_code
