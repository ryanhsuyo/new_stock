# current_rules.md — 當前交易 / 訊號規則總表

本文件是每次處理股票策略、訊號、候選股、進出場價格、盤後筆記與 Dashboard 呈現前的「快速規則總表」。

詳細欄位規格與完整定義仍以 `backend/docs/signal_rules.md` 為準；本文件負責整理目前實際採用的判斷優先順序與操作語氣。

---

## 1) 核心定位

- 系統提供的是「技術位置、風險水位與隔日計畫」，不是保證式投資建議。
- 不輸出「一定會漲、重壓、保證獲利、精準高低點」。
- 所有分數、訊號與建議都必須有 `reasons`、`risk_note`、`no_buy_reason` 或 `daily_checklist` 可解釋。
- 每次正式訊號輸出必須附 `rules_version` 與 `rules_metadata`，用來稽核當次策略 profile、策略 ID 與主要參數快照；此欄位不可被前端當成新買賣訊號。
- 正式訊號以收盤日線為準；盤中只做監控，不直接覆蓋正式 `summary.json`。
- 前端與 API 的 `close` / `current_price` / `current_value` 預設都來自 `backend/data/ohlcv.csv` 的最新收盤價，不是即時市價；畫面文字應標示為「收盤」「最新收盤」或「收盤估值」，避免誤解成盤中報價。
- 技術分析頁必須直接顯示價格基準提示；買入 / 賣出 modal 若用最新收盤價預填，必須提醒使用者改成真實成交價。
- 技術分析頁若單檔不在 `leaders.json`，可提供「加入追蹤清單」修復入口；此入口只更新 `leaders.json` / `stock_names.json`，不得直接觸發長時間回補或正式訊號計算，下一步仍提示使用者執行 `daily_update.py`，避免只 backfill 但忘記刷新報表與 Daily Check。
- 技術分析頁若單檔已追蹤但 `ohlcv.csv` 無資料或資料不足，應顯示修復步驟與可複製指令，引導使用者手動執行 `daily_update.py` 進行回補、重算訊號與刷新 Daily Check。
- 技術分析頁與加入追蹤 API 的修復資訊應同時提供短版 `next_action_command`（畫面閱讀）與完整 `next_action_copy_command`（內含 `cd backend`，供複製執行）。
- Dashboard 應集中顯示已追蹤但缺日線或日線不足的資料修復隊列；此隊列只做發現與複製修復指令，不直接啟動長時間回補。
- 缺日線或日線不足的大範圍修復指令統一使用 `python3 scripts/daily_update.py --months 12`；此入口會補 OHLCV、重算訊號並刷新 Daily Check，避免只 backfill 但忘記重算輸出。
- `daily_check.json` 必須納入資料修復摘要（缺日線 / 資料不足數量、Top 待修復股票與修復指令），並把該摘要列入 PM Top actions；此檢查只讀取 universe 狀態，不直接啟動長時間回補。
- `daily_check.json.top_actions[*].action_payload` 可提供複製清單、複製指令、檔案路徑或既有 API 導引；command 類 payload 應提供 `copy_command` 作為完整可貼上指令，並提供 `expected_outputs` 說明執行後應檢查的產物。Dashboard 只能呈現或複製此 payload，不得在前端新增交易或策略判斷。
- `expected_outputs` 的指令對應必須集中維護在後端共用契約，避免 `doctor.py`、`daily_check.py`、PM Worklist 與 workflow service 對同一指令列出不同產物；目前 `run_signals.py` 也會刷新 `daily_check.json`。
- `daily_check.json.top_actions[*].action_payload.kind="copy_text"` 時，後端應附 `preview_items`，列出前幾個可直接呈現的股票 / 待辦項目；前端或文字報告不應自行解析大段 `copy_text` 才能顯示摘要。
- `daily_check.py` 文字輸出必須把 action payload 的重點印出來：command 的預期產物、copy_text 的預覽清單、file 的目標路徑、api 的方法與端點、以及候選股復盤缺少的代碼，避免 PM 摘要只剩「請去 Dashboard 看」。
- `GET /api/system/daily-check` 讀取舊的 `daily_check.json` 時，後端必須補上 `snapshot_is_stale`、`snapshot_stale_reason`、`snapshot_refresh_command`、`snapshot_refresh_copy_command` 與 `snapshot_refresh_expected_outputs`；Dashboard 必須把非今日產生的快照標示為需刷新，並提供可複製刷新指令，避免隔天誤用昨日 PM 摘要。
- `GET /api/system/update-workflow` 是每日更新流程的單一狀態入口，負責彙整資料是否過期、交易輸出是否落後、Daily Check 是否需刷新，以及下一個可複製指令；此 API 不新增交易訊號，也不直接執行長時間回補。
- 若 Daily Check 快照是今日版本但 `can_use_trade_outputs=false`，Update Workflow 必須視為 `blocked`，並沿用 Daily Check 的第一個 blocker / top action 作為 `next_action`，不得顯示 ready。
- Update Workflow 沿用 Daily Check blocker / top action 時，必須保留原本的 `action_payload`，讓 API / copy_text / file 類待辦在 Dashboard 上仍可操作，不可只留下 `command` 字串。
- Update Workflow 的 `next_action.command` 可保留短指令供畫面閱讀；若要提供複製按鈕，應優先使用 `next_action.copy_command`，內含 `cd backend` 所需工作目錄，避免使用者在錯誤目錄執行失敗。
- Update Workflow 的 `next_action.expected_outputs` 必須列出跑完指令後應檢查的主要產物；`daily_update.py` 流程至少包含 `ohlcv.csv`、`update_status.json`、`data_coverage_report.json`、`summary.json`、`universe_report.csv`、`daily_brief.json` 與 `daily_check.json`。
- `daily_update.py` / `update_all_data.py` 若在 backfill、基本面同步或 signals 重算途中被中斷，必須把 `update_status.json.last_run_status` 寫成 `failed` 並附中斷原因，避免 Dashboard 長期誤顯示 running。
- `daily_update.py` / `update_all_data.py` 由 CLI 執行時，應串流顯示 backfill / chips 子程序進度，避免長時間無輸出被誤判為卡死；API 背景更新可保留安靜模式。
- `daily_update.py` / `update_all_data.py` CLI 收到使用者中斷時應乾淨回傳 exit code `130`、釋放 PID lock 並寫入中斷 log，不應噴出長 traceback。
- `update_status.json.last_run_status="running"` 若超過 2 小時或缺少開始時間，API 應視為 `stalled`，Dashboard 應提示可重新啟動每日更新，不得永久擋住手動更新。
- 舊版 `GET /api/system/workflow-status` 的 `next_actions[*]` 與 `decision_guardrails` 也需提供完整 copy command；`command` / `required_action` 保留短版供閱讀，`copy_command` / `required_action_copy_command` 供貼上執行。
- 舊版 `GET /api/system/workflow-status` 的 `next_actions[*]` 也應提供 `action_payload`；command 類 payload 包含 `copy_command` / `expected_outputs`，API 類 payload 包含 `method` / `endpoint`，讓前端不必為新舊工作流入口各寫一套操作解析。
- 舊版 `workflow-status.decision_guardrails` 若阻擋交易輸出，除了 `required_action` / `required_action_copy_command`，也必須提供 `required_action_expected_outputs` 與 `action_payload`，讓最後風控閘門本身就能說明「要跑什麼、在哪裡跑、跑完檢查什麼」。
- Dashboard 首頁 PM Worklist 必須由後端 `/api/system/pm-worklist` 彙整 Update Workflow、資料修復、基本面避雷補資料、候選股復盤與 Daily Check 待辦；若 Update Workflow 顯示資料或交易輸出阻塞，必須排在 PM Worklist 最前面，並把 `next_action.expected_outputs` 傳入 `action_payload.expected_outputs`。資料修復項也必須提供 `copy_command` 與 `expected_outputs`。需要長時間執行的資料更新只複製指令或導引，不直接啟動；候選股復盤這類已定義的安全批次動作可限量寫入 `decision_journal`，但不得修改交易紀錄、持倉或現金。
- `/api/system/pm-worklist` 必須回傳 `primary_action`，代表 Dashboard 第一屏唯一最優先待辦；此欄位由後端 service 排序後產生，前端不得自行重建優先順序或用多張同權重卡片取代主待辦。
- `/api/system/pm-worklist` 必須回傳 `today_focus`，代表 Dashboard 第一屏的今日焦點契約；每筆至少包含 `category`、`code`、`name`、`label`、`reason`、`next_action`、`severity`、`source`、`price_basis`、`as_of`。分類順序固定為 `portfolio_risk`、`entry_candidate`、`review_needed`，每類最多 3 筆；持股風險永遠優先於候選股。若交易輸出 blocked 或資料過期，`today_focus` 不得把候選股包裝成可交易進場訊號，只能提示先解除阻塞。
- Dashboard 第一屏應以 Decision Console 呈現資料日、交易輸出可用性、價格基準、Primary Action、大盤姿態與今日焦點；完整 Update Workflow、Daily Check、PM Worklist 明細與檔案狀態應放在下方，避免第一屏資訊過載。
- 單檔訊號計算必須有 timeout 保護；逾時股票只可輸出 `DATA_MISSING` / `data_ok=false`，並提供 `calculation_status=timeout`、`calculation_error`、`no_buy_reason` 與 `risk_note`。逾時不得中止其他股票，但非 timeout 的未知例外仍應中止並回報，避免默默吞錯。
- `summary.json` 必須回報單檔 timeout 秒數、數量與股票代碼；`universe_report.csv` 必須保留 `calculation_status` / `calculation_error`，讓空推薦或缺資料結果可追溯。
- Dashboard PM Worklist 明細應分組呈現，至少區分阻塞 / 資料修復、候選復盤、基本面與 Daily Check / 維護；動作按鈕需共用 action handler，依 `action_payload.kind` 處理 command、copy_text 與安全 API 導引，不得在各卡片重複分散實作。
- PM Worklist 若收斂 Daily Check 的非重複待辦，必須保留 Daily Check 原本的 `action_payload`；copy_text 類 payload 同樣應提供 `preview_items`，避免 Dashboard 入口比 Daily Check 少資訊。
- 持倉與持股分析以 `backend/data/trades.json` 為主要來源自動推算；`positions.json` 僅保留為舊格式備援或狀態檢查，不應要求使用者手動維護。
- 由交易紀錄推算持股均價時，買進成本必須包含買進手續費；訊號、候選報告、投組頁與持股分析的持股均價口徑需一致。
- 單股技術分析的上升 / 下降趨勢線優先使用多點確認：擺盪點距投影線 2% 內視為有效觸點，至少三個觸點才標示多點確認；上升支撐被低點向下超過 2% 或下降壓力被高點向上超過 2% 時，該候選線失效。API 仍只回傳定義斜率的 `p1/p2`，沒有多點候選時保留既有最近兩點規則。

---

## 2) 訊號優先順序

目前固定兩種推薦策略：

- `old_wang`：老王短波段 / 大盤籌碼輪動，負責強勢族群、短均線、跳空、爆大量低點 / 高點與不追高判斷。
- `steady_momentum`：Quality Momentum Lite，負責中期趨勢、相對強度、進場位置、風險報酬、過熱控制與輕量基本面避雷。
- `core_technical_v2` 仍是內部技術訊號引擎，負責產生 `BUY` / `SELL` / `HOLD`、價格計畫與風控欄位，但不再作為獨立推薦桶。
- Dashboard / Universe Report 只能把 `old_wang` 與 `steady_momentum` 作為推薦策略；未符合這兩者者應歸為觀察 / 暫不進場，內部技術訊號只作為解釋欄位。
- 基本面避雷資料流程保留為 `steady_momentum` 的避雷輔助與 PM 補資料流程，不作為獨立候選股策略；`fundamental_*` 為目前正式基本面輔助欄位。
- 基本面避雷補資料流程必須由後端 `fundamentals-status.workflow_summary` 提供 PM 階段、主要下一步、checklist 與焦點股票；前端只呈現此摘要，不自行重建流程規則。
- 外部整理好的基本面數字應先用 `python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv` dry-run 匯入預覽，再用 `--apply` 寫入 `backend/out/fundamentals_priority_fill.csv`；正式合併仍需走 `merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS`，不得直接偽造或跳過驗證寫入 `fundamentals.json`。
- 官方基本面暫存報告可用 `GET /api/system/fundamentals-official/status` 查狀態，並可用 `POST /api/system/fundamentals-official/reports` 產生 report-only CSV；此 API 僅寫 `backend/out/official_fundamentals_*.csv`，不得直接 apply 至 priority CSV 或策略輸入。
- 官方 API 目前只穩定接入可直接取得的參考欄位：TWSE BWIBBU 的 PE / PB / 殖利率、TWSE 月營收 YoY / 累計營收 YoY、TPEx PE / PB / 殖利率、TWSE/TPEx 營益分析 report-only 參考欄位，以及 TWSE/TPEx 一般業資產負債表 report-only 參考欄位。正式自動寫入 priority CSV 目前僅允許 TWSE/TPEx 官方 PE 直接映射到 `pe`；ROE、EPS、FCF、interest coverage 等財報推導欄位仍需穩定官方財報來源與公式確認，未確認前不得偽造。

推薦策略固定維持 `old_wang` 與 `steady_momentum`；若需要混合判斷，應在單檔說明裡呈現「共振」，不要另開 `combined` 推薦桶。

策略共振欄位：

- `strategy_alignment`：`strong_alignment` / `single_strategy` / `conflict` / `no_alignment`
- `aligned_strategies`：列出同向支持的推薦策略，例如 `old_wang`、`steady_momentum`
- `strategy_conflict_notes`：列出衝突原因；內部技術訊號若已出場或失效，老王 / 穩健動能不得覆蓋風控結論。
- 共振只做排序、解釋與觀察輔助，不新增第四套推薦桶，也不改寫各策略原始判斷。

內部訊號：

- `entry_confirmed`：入場確認
- `ready_to_enter`：準備入場
- `watchlist`：觀察中
- `hold`：持股續抱
- `take_profit_warning`：停利觀察
- `exit_warning`：出場警示
- `invalidated`：趨勢 / 型態失效
- `DATA_MISSING`：資料不足

對外相容：

- `entry_confirmed` / `ready_to_enter` 對外仍可映射 `BUY`
- `watchlist` / `hold` / `take_profit_warning` 對外為 `HOLD`
- `exit_warning` / `invalidated` 對外為 `SELL`

候選股復盤紀錄：

- 候選股報表的快速復盤只寫 `backend/data/decision_journal.json`，不得修改交易紀錄、持倉或現金。
- 未持有股票若報表動作為 `exit` / `reduce`，決策日誌應記為 `skip`（不進場），不得記成 `sell` 或 `reduce`。
- Dashboard / Universe Report 可提供批次記錄入口，但應限制批次數量並清楚提示不會修改持倉或交易紀錄。
- 候選股報表復盤流程必須由後端 `decision-journal/universe-report-workflow` 提供 PM 階段、主要下一步、checklist 與 Top 待復盤股票；前端只呈現摘要與觸發批次建立，不自行重建規則。
- 決策日誌新增、批次新增、更新或刪除後，必須刷新 `backend/out/daily_check.json`，讓 Dashboard / Workflow 的待辦燈號反映最新復盤狀態。

判斷語氣：

- `ready_to_enter` 是「可小試 / 可分批」，不是大力買入。
- `watchlist` 是「等區間 / 等量價確認」，不是現在買。
- `take_profit_warning` 是「不追價、注意減碼」，不是立即全出。
- `exit_warning` 是「趨勢或關鍵支撐破壞，需要處理」。

---

## 3) 大盤規則

一般大盤濾網：

- 第一版以 `0050` 判斷 `market_regime` 與 `market_filter`。
- `0050` 站上 MA20 / MA60 且 MA60 向上，市場偏多。
- 跌破 MA60 時，市場偏空，做多訊號降權。

老王大盤濾網：

- 優先使用 `TSE` / `OTC` 指數；資料不足時以 `0050` 代理。
- 觀察 MA5、MA10 與爆大量低點。
- `TSE` / `OTC` 同時守 MA5 / MA10 與爆大量低點，視為偏多。
- 跌破爆大量低點，轉風險。
- 未守 MA5 / MA10，轉保守或封鎖追價。

人工盤後筆記：

- `backend/data/market_notes.json` 可記錄人工貼上的大盤 / 櫃買 / 美股廣度 / 個股範例筆記。
- 可用 `GET /api/stocks/market-notes` 查看目前筆記，或用 `POST /api/stocks/market-notes` 依日期新增 / 覆蓋筆記，避免手動編輯 JSON 格式錯誤。
- 寫入 `summary.json.manual_market_note` 後供 Dashboard 顯示。
- 人工筆記只做風控提示，不直接改寫正式 `BUY` / `SELL` / `HOLD`。
- 筆記若距離訊號基準日超過 2 個交易日，會標記 `is_stale=true` 與 `update_required=true`；Dashboard 顯示需更新，`daily_brief.json` 不再沿用該筆記的水位與隔日 checklist。
- Dashboard 的人工筆記表單預設日期必須使用訊號資料日 / workflow `data_as_of`，避免用系統日誤存到尚未收盤或無資料的日期。
- Dashboard 可提供「沿用舊筆記」作為草稿起點，但只能填入表單，不可自動儲存或自動重算；使用者仍需更新今天盤勢後手動儲存。
- `summary.json.manual_market_note.playbook` 與 `daily_brief.json.manual_playbook` 會從最新人工筆記自動整理出水位、風險姿態、焦點族群、風控條件與觀察代碼；若筆記過期，`daily_brief` 不沿用該 playbook。
- `daily_brief.json.manual_watchlist_review` 會依人工筆記的觀察代碼順序，逐檔對照正式訊號，輸出續抱、等回測、可分批、優先處理風險或不在追蹤清單；此欄位只做解釋與復盤，不覆蓋正式訊號。
- 可用 `GET /api/stocks/signals/manual-watchlist-review` 讀取精簡版人工觀察股校正表，供 Dashboard 或報表頁直接呈現，避免前端解析整包 `daily_brief.json`。

---

## 4) 2026-05-27 盤後風控規則

此規則來自人工盤後筆記，優先於 2026-05-14 的五成水位語氣。

- 短線資金持股水位提高至約七成，但仍不追沒有量價確認的高檔股票。
- 美股 S&P 500、Nasdaq、費半與 AI / 半導體主線再度走強，短線資金偏向科技與半導體。
- 台股加權 2026-05-27 放量突破前高並創高，代表新一段多頭波段成立；短線優先看 MA5，波段看 MA10。
- 櫃買 2026-05-27 同步創高並維持出量，短線仍強；若後續量縮或跌破 MA5，才轉保守。
- 突破後不因單日長黑或開高震盪直接判定結束，只要大量低點、MA5 / MA10 或月線支撐守住，強勢股續抱。
- 量能是強勢股續航關鍵：出量續攻可續抱，量縮轉弱才降低追價與持股。
- 仍需汰弱留強：水位提高到七成不代表弱勢股可忽略，跌破支撐或轉弱者仍優先處理。
- 目前強勢族群優先觀察：記憶體、AI / 半導體、ABF / 載板、PCB / 散熱、被動元件與電源周邊。

範例觀察：

- `3481 群創`：突破前高後仍鎖住漲停，爆大量低點與 MA5 是短線重點，未跌破前續抱觀察。
- `2344 華邦電`：重新站回 MA5 / MA10 並突破前高，記憶體主線轉強，短線看 MA5。
- `2408 南亞科`：守月線與 MA20，量能未縮代表人氣仍在，短線震盪仍以續抱觀察。
- `2337 旺宏`：仍須突破 178.5 前高壓力，若持續出量可挑戰前高；記憶體族群中屬補漲觀察。
- `6770 力積電`：守五日線並持續創高，出量續攻可續抱，量縮才轉弱。
- `3006 晶豪科`：回到 MA5 / MA10 強勢創高格局，突破前高才是海闊天空確認。
- `2454 聯發科`：短線減碼看 MA5，站回 MA5 / MA10 後轉強；AI / TPU 題材與大摩目標價上修支撐強勢語氣。
- `3037 欣興`、`8046 南電`：長線看月線 / MA20，南電守住多方缺口與三條短均線則維持多方趨勢。

## 4.1) 2026-05-14 盤後風控規則

此規則來自人工盤後筆記，優先於 2026-05-13 的短線語氣。

- 短線資金持股水位維持約五成，不因單日反彈直接升回七成。
- 美股 AI / 半導體主線反彈，但 PPI 等通膨壓力仍使降息預期承壓，風控不可放掉。
- 台股加權 2026-05-14 反彈並守住 MA10，但尚未有效突破前高，先視為多頭波段續命而非全面追價。
- 櫃買 2026-05-14 守 MA5 並維持創高格局，短線強於加權，但仍需觀察 MA10。
- 上漲家數仍低於下跌家數，盤面分歧，選股必須集中在強勢族群。
- 降低持股水位時執行「汰弱留強」：先處理跌破短均、跌破爆大量低點或族群轉弱的股票。
- 強勢股若守住 MA5 / MA10、多方缺口或爆大量低點，不因單日漲多、上影線或高檔震盪就直接視為頭部。
- MA5 失守但 MA10 守住：由追價轉觀察，不直接判定波段結束。
- MA10 失守：波段轉弱，持股者進入減碼或停損檢查。
- 前高突破若搭配 MA5 / MA10 向上與量能延續，列強勢確認；尚未突破前高者列觀察，不追價。
- 目前強勢族群優先觀察：記憶體、被動元件 / 電源周邊。

範例觀察：

- `2408 南亞科`：突破前高壓力與多方缺口後轉強，守缺口與 MA5 / MA10 則續抱觀察。
- `2344 華邦電`：守 MA5 可維持創高格局，波段仍看 MA10；前高 136 附近是下一道壓力。
- `2337 旺宏`：守月線 / MA20 仍維持多方趨勢，178.5 前高突破才是下一段確認。
- `3006 晶豪科`：守多方缺口並突破前高，列記憶體補漲強勢觀察。
- `2492 華新科`、`5328 華容`、`6175 立敦`、`2472 立隆電`、`3026 禾伸堂`：列入被動元件 / 電源周邊觀察，優先看 MA5 / MA10、爆大量低點與前高壓力。

## 4.2) 2026-05-13 盤後風控規則

此規則來自人工盤後筆記，除非後續筆記更新，先作為目前短線風控語氣。

- 美股 S&P 500 創高但內部廣度不足，低於 60% 成分股站上 50 / 200 日均線，代表內部結構有背離風險。
- 台股加權與櫃買 2026-05-13 跌破 MA5，短線轉弱。
- 短線資金持股水位降至約五成。
- 跌破 MA5：降低追價與加碼意願。
- 跌破 MA10：波段行情降溫，持股水位再下修。
- 強勢股不因單日長黑直接判定行情結束，仍看 MA10、爆大量低點與前高壓力。
- 爆大量低點未破：仍可觀察。
- 爆大量低點跌破：隔日計畫被破壞，轉風險處理。
- 弱勢或跌破關鍵短均者優先減碼，保留能守短均與大量低點的個股。

範例觀察：

- `3481 群創`：量價強，短線弱弱減碼看 MA5，突破行情看 MA10。
- `2409 友達`：守爆大量低點與短均線，前高壓力需突破。
- `2303 聯電`：爆大量低點與 MA5 是重要支撐，雙破時持股者優先減碼。

---

## 5) 個股內部技術規則

先看長線，再看短線：

- 長線使用 MA60 / Stage / 相對強度。
- 短線使用 MA5 / MA10 / MA20、支撐壓力、型態與量能。
- 長線偏空時，短線多頭訊號只能列觀察或降權。

支撐壓力：

- 使用區間，不追求單點精準。
- 支撐 / 壓力至少要能解釋來源，例如 MA20、爆大量低點、近期高低點、缺口。
- 進場、停損、停利必須同時輸出，並附 `price_plan_note`。
- `support_source`、`resistance_source`、`entry_source`、`stop_source`、`target_source` 是稽核欄位，只解釋價格來源，不新增買賣條件。

回測口徑：

- 第一版只驗證 `core` 正式日線訊號；訊號在 D 日收盤後成立，只能在下一個交易日開盤成交。
- 每次計算只能看到訊號日以前的個股與 0050 資料；目前籌碼、基本面、人工筆記與正式持倉不得帶入歷史回測。
- 買賣價格必須加入對策略不利的滑價，手續費、折扣、最低手續費與賣出證交稅沿用正式交易金額口徑。
- 預設保留期末未平倉部位，並以最後收盤估算扣除賣出費稅後的淨值；強制平倉必須是明確選項。
- 回測結果只能用於規則驗證，不是獲利保證；至少輸出交易明細、總報酬、最大回撤、勝率與 buy-and-hold 比較。

風險報酬：

- `reward_risk_ratio` 是進場品質重要條件。
- 趨勢強但 R/R 不足，應列 `watchlist` 或 `no_buy_reason`，不可硬推 `ready_to_enter`。
- RSI 過熱但仍守 MA5 / MA10，不預設高點；跌破短均再轉保守。

型態風險：

- 頭肩頂使用三個擺盪高點：左右肩差距不超過 10%，頭部至少高於雙肩 3%，兩段回落低點的較低者作為保守頸線。
- `head_and_shoulders_top forming` 只做風險警示與 `-10` 排序降權，不得單獨強制 SELL。
- 收盤跌破頸線才是 `confirmed`，給 `-20` 風險降權並寫入 `risk_note`；收盤有效突破頭部則型態 `failed`，移除空方懲罰並寫入 `reasons`。

---

## 6) 老王大盤籌碼輪動規則

老王 tag 是輔助旗標，不覆蓋主訊號。

成立條件方向：

- 大盤濾網不可為 `block`。
- 族群輪動要轉強，例如 AI 半導體、ETF 等族群的 20 / 60 日表現與站上 MA20 比例改善。
- 個股需符合至少一種轉強型態：
  - `leader_breakout`
  - `ma60_reclaim`
  - `low_hold_rebound`
  - `sector_catch_up`
  - `previous_high_breakout`
  - `volume_high_breakout`
  - `all_ma_reclaim`

風控原則：

- 不看單一 K 線。
- 量能不足時不可只因紅 K 觸發強買。
- 前高突破後不因漲幅大就自動視為頭部，要看 MA5 / MA10 / MA20 / MA60、爆大量低點、缺口與量能。
- 短線噴出且遠離 MA20 時，支撐改看 MA10。
- 5 / 10 / 20 / 60 全破，前高 / 頭部風險升高。

---

## 7) 基本面避雷資料規則

基本面避雷欄位目前只作為補資料流程與穩健動能的輔助分數，不再是獨立推薦策略。`fundamental_*` 是正式基本面輔助欄位，文件或 UI 不應把它稱為策略。

資料來源：

- `backend/data/fundamentals.csv`：手動整理或外部資料來源匯入的工作檔
- `backend/data/fundamentals.json`
- 格式可參考 `backend/data/fundamentals.example.json`
- leaders 股票清單變動後，`python3 scripts/daily_update.py` 會自動補齊 CSV row；也可手動跑 `python3 scripts/sync_fundamentals_template.py`
- 外部資料優先使用 `python3 scripts/prepare_fundamentals_priority_import.py --write-template` 產生模板，再用 `/path/to/source.csv` dry-run，確認後以 `--apply` 寫出 `backend/out/fundamentals_priority_fill.csv`
- 官方資料第一版使用 `python3 scripts/update_fundamentals_official.py` 從 TWSE / TPEx 官方來源補 priority CSV；目前只將 TWSE `BWIBBU_ALL.PEratio` 與 TPEx daily PE 直接映射到 `pe`。也可加 `--write-report` 寫出 `backend/out/official_fundamentals_twse_bwibbu.csv` 保存 `DividendYield` / `PBratio` 官方暫存參考欄位。PB、殖利率與其他暫存欄位不硬塞進既有評分欄位。
- 官方月營收第一版可用 `python3 scripts/update_fundamentals_official.py --write-monthly-revenue-report` 寫出 `backend/out/official_fundamentals_twse_monthly_revenue.csv`，保存 TWSE 上市公司月營收 YoY / 累計營收 YoY 官方暫存參考欄位；目前不寫入 `fundamentals.csv` 評分欄位，也不補上櫃資料。
- TPEx 上櫃 PE/PB/股利第一版可用 `python3 scripts/update_fundamentals_official.py --write-tpex-daily-pe-report` 寫出 `backend/out/official_fundamentals_tpex_daily_pe.csv`，保存上櫃公司本益比、每股股利、殖利率、股價淨值比與財報年季官方暫存參考欄位；其中 PE 可直接映射到 priority CSV 的 `pe`，但 PB、殖利率、股利與財報年季仍不寫入 `fundamentals.csv` 評分欄位。
- TWSE/TPEx 營益分析第一版可用 `python3 scripts/update_fundamentals_official.py --write-profitability-report` 寫出 `backend/out/official_fundamentals_profitability.csv`，保存營業利益率、稅前純益率與稅後純益率官方暫存參考欄位；目前只做 report-only，不寫入 `operating_margin_5y_avg` 或任何正式基本面欄位。
- TWSE/TPEx 一般業資產負債表第一版可用 `python3 scripts/update_fundamentals_official.py --write-balance-sheet-report` 寫出 `backend/out/official_fundamentals_balance_sheet.csv`，保存資產總額 / 總計、負債總額 / 總計與權益總額 / 總計官方暫存參考欄位；目前只做 report-only，不寫入 `debt_to_equity`、`roe_5y_avg` 或任何正式基本面欄位。金融、保險、證券期貨、金控與異業 variant 需另補 fixture 測試後才能接入。
- TWSE/TPEx 一般業損益表第一版可用 `python3 scripts/update_fundamentals_official.py --write-income-statement-report` 寫出 `backend/out/official_fundamentals_income_statement.csv`，保存營業收入、營業利益、本期淨利與基本每股盈餘官方暫存參考欄位；目前只做 report-only，不寫入 `eps_growth_5y_cagr`、`revenue_growth_5y_cagr`、`roe_5y_avg` 或任何正式基本面欄位。金融、保險、證券期貨、金控與異業 variant 需另補 fixture 測試後才能接入。
- TWSE/TPEx 股利分派第一版可用 `python3 scripts/update_fundamentals_official.py --write-dividend-report` 寫出 `backend/out/official_fundamentals_dividend.csv`，保存股利年度、期別、每股現金股利與每股股票股利官方暫存參考欄位；目前只做 report-only，不寫入 `dividend_years` 或任何正式基本面欄位，也不推導連續配息年數。
- 官方 report-only 覆蓋率稽核可用 `python3 scripts/update_fundamentals_official.py --write-coverage-audit` 寫出 `backend/out/official_fundamentals_coverage_audit.json`，用 priority CSV 股票清單檢查各官方暫存報告是否存在、是否有對應列與關鍵欄位；此稽核只讀取暫存報告，不寫入 priority CSV 或正式基本面欄位。
- 官方 report-only 覆蓋率也可用 `GET /api/system/fundamentals-official/coverage-audit` 查詢；此 API 只讀取既有 priority CSV 與官方暫存報告，不觸發官方 API 抓取，也不產生或改寫任何資料檔。若 priority CSV 不存在，應回傳清楚 404。
- Dashboard 可呈現官方 report-only 覆蓋率稽核摘要，但只能使用後端 `coverage-audit` 回傳的 `target_count`、`coverage_pct`、`missing_report_files` 與 `next_action_label`，不得在前端重算覆蓋率或推導正式基本面欄位。
- Daily Check / PM Worklist 可呈現官方 report-only 覆蓋率待辦，但只能讀取 `coverage-audit` 狀態；不得在 Daily Check 或 PM Worklist 觸發官方 API 抓取、產生 report-only CSV、合併 priority CSV 或寫入正式基本面欄位。PM Worklist 平常應沿用 Daily Check top action，只有 Daily Check 快照缺失或過期時才直接讀取 audit 作為 fallback。
- Quality Momentum Lite guard 覆蓋率摘要必須保持 read-only：`pe` 是目前唯一可直接 apply 的官方欄位；營益率、負債 / 權益輸入、月營收 YoY 與 EPS 只能作為 report-only / derived-input 參考，不得從單期報告列推導 `*_5y_avg`、5 年 CAGR 或正式 `debt_to_equity`。
- Quality Momentum Lite guard 覆蓋率可用 `GET /api/system/fundamentals-official/quality-momentum-lite-guard` 查詢；此 API 只讀取既有 priority CSV 與官方 report-only CSV，不觸發官方 API 抓取、不產生報告、不寫入 priority CSV 或正式基本面欄位。
- 11 個正式基本面欄位保留為進階資料格式；但 `steady_momentum` 不再要求 11 欄完整才能運作。Quality Momentum Lite 只使用低成本 guard 欄位：`pe`、`operating_margin_5y_avg`、`debt_to_equity`、`revenue_growth_5y_cagr`、`eps_growth_5y_cagr`。其餘 ROE、FCF、interest coverage、dividend years 等欄位只能作為進階參考，不得因缺值阻塞第二策略。
- F7 官方財報來源決策已確認 TWSE / TPEx OpenAPI 有損益表、資產負債表、營益分析與股利分派來源，可作為 report-only probe 候選；但尚未確認現金流量表 / 資本支出來源，因此 `free_cash_flow_positive_years`、`operating_cash_flow_to_net_income`、`fcf_yield` 仍維持 blocked，不得自動填值。
- 正式合併使用 `python3 scripts/merge_priority_fundamentals.py` 預覽，再用 `--apply --confirm MERGE_PRIORITY_FUNDAMENTALS` 寫回 `fundamentals.csv` 並匯入 `fundamentals.json`
- `python3 scripts/daily_update.py` 會在重算 signals 前自動同步並匯入 `fundamentals.csv`
- 覆蓋率檢查使用 `python3 scripts/check_fundamentals.py`

Dashboard 補資料流程：

- 先產生 `fundamentals_priority_import_template.csv` 或下載優先補資料清單，只補優先觀察股票，不必一次補完全部 leaders。
- 使用外部 CSV 匯入前必須先 dry-run；不得直接偽造或手動改寫 `fundamentals.json`。
- 重新產生 / 下載 priority CSV 時，必須保留既有已填的必要欄位，只刷新輔助說明欄位，避免覆蓋使用者已填資料。
- 若既有 priority CSV 有格式錯誤值，也應保留原始輸入並由預覽 / validation 指出錯誤，不可因刷新 CSV 直接崩潰或靜默清空。
- Dashboard 應顯示 priority CSV validation 的前幾筆錯誤 / 警告，包含列號、股票代碼、欄位與錯誤值，讓使用者能直接回 CSV 修正。
- Dashboard 可顯示官方基本面暫存報告狀態（檔案是否存在、row count、mtime 與 report-only 下一步）；此區只做可觀測性，不代表 11 個必要基本面欄位已補齊，也不得在前端推導分數。
- Dashboard 可提供官方暫存報告的 report-only 產生按鈕，但只能呼叫後端 `POST /api/system/fundamentals-official/reports` 並固定非 apply；成功後只刷新官方報告狀態，不得直接寫入 priority CSV 或策略輸入。
- Dashboard 應提供「複製補資料清單」，列出優先 10 檔、每檔缺少欄位與欄位範例值，讓使用者可直接照清單補 `fundamentals_priority_fill.csv`。
- `python3 scripts/check_fundamentals.py` 應輸出 priority CSV 狀態、下一步、錯誤 / 警告數與第一筆問題，保持 CLI、Dashboard 與 Workflow 的語氣一致。
- 填完 `backend/out/fundamentals_priority_fill.csv` 後，CLI 應使用 `python3 scripts/merge_priority_fundamentals.py` 先預覽；確認可合併後才使用 `python3 scripts/merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS` 正式合併。
- 百分比欄位填 `28.5` 代表 28.5%，不要填 `0.285`。
- 空白或部分填寫的 priority CSV 只能預覽，不能正式合併。
- 至少一檔股票 11 個必要欄位完整，才可合併回 `fundamentals.csv` 並匯入 `fundamentals.json`。
- 預覽合併必須回報可合併檔數、部分填寫檔數、空白檔數、格式警告與基本面避雷預覽試算；payload 使用 `fundamental_preview` 時，只能視為正式基本面預覽欄位，不可視為推薦策略。
- Dashboard 顯示基本面避雷預覽時，除總分外必須顯示品質 / 安全 / 估值 / 成長四組分數，避免只看總分而不知道卡在哪一類。
- 正式合併後必須重新產生訊號，基本面避雷分數才會進入 `summary.json` / `universe_report.csv`。
- Dashboard 在正式合併成功且 `signals_refresh_required=true` 時，必須直接提供「重新產生訊號」入口，避免使用者忘記刷新基本面避雷結果。
- CLI 正式合併成功後，必須提示重跑 `python3 scripts/run_signals.py`，並更新 `fundamentals_report.json` 供 Dashboard / doctor 讀取。
- Workflow 若偵測到 priority CSV 已可合併，下一步應提示「合併基本面避雷補資料」而不是只顯示一般缺資料提醒。
- Workflow 若偵測到 priority CSV invalid，應升級成 danger 待辦，並在 detail 顯示第一筆錯誤 / 警告的列號、代碼、欄位與值。

必要欄位方向：

- `roe_5y_avg`：5 年平均 ROE
- `operating_margin_5y_avg`：5 年平均營業利益率
- `free_cash_flow_positive_years`：近 5 年自由現金流為正年數
- `operating_cash_flow_to_net_income`：營業現金流 / 淨利
- `debt_to_equity`：負債權益比
- `interest_coverage`：利息保障倍數
- `revenue_growth_5y_cagr`：營收 5 年 CAGR
- `eps_growth_5y_cagr`：EPS 5 年 CAGR
- `pe`：本益比
- `fcf_yield`：自由現金流殖利率
- `dividend_years`：連續配息年數

評分拆分：

- `fundamental_quality_score`：品質
- `fundamental_safety_score`：財務安全
- `fundamental_value_score`：估值
- `fundamental_growth_score`：成長

使用條件：

- `fundamental_flag=true` 代表 Quality Momentum Lite 的輕量基本面避雷成立，可作為 `steady_momentum` 的輔助加分參考。
- 此資料不產生獨立候選股推薦桶，不覆蓋老王或穩健動能的風控結論。
- 缺少 `fundamentals.json` 時，必須回傳 `fundamental_data_ok=false` 與缺資料原因。
- 若單檔已有任一 lite guard 欄位即可先評分，缺資料不直接淘汰第二策略，只降低信心或顯示 `lite_guard_partial`。
- 部分資料評分必須輸出 `fundamental_data_completeness_pct`、`fundamental_missing_fields`、`fundamental_scored_groups`，但完整度以 lite guard 欄位計算，不以 11 欄進階資料計算。
- 完全沒有 lite guard 欄位時維持 `fundamental_data_ok=false`，並在缺資料原因說明缺少哪些 lite guard 欄位。

---

## 8) 每日作戰輸出

每檔股票應輸出：

- `daily_action`
- `daily_action_label`
- `daily_action_identity`
- `daily_action_reason`
- `daily_key_price`
- `daily_invalidation`
- `daily_priority`
- `daily_checklist`

每日作戰檢查表至少包含：

- `market`：大盤是否可做
- `setup`：個股型態或關鍵支撐
- `risk`：風險報酬、RSI、長線風險
- `action`：隔日動作與失效條件

資料狀態：

- `daily_brief.data_status`：每天看作戰表前先看此欄，確認資料最新日、產生時間、覆蓋率與 stale 狀態。
- `GET /api/system/data-status` 的 `last_run_status` 可為 `success` / `failed` / `running` / `stale` / `null`；`stale` 代表更新流程跑完但資料仍過期，不可當成功。
- 若手動執行 backfill / run_signals 後 `summary.json.as_of` 比 `update_status.json.last_data_as_of` 新，`data-status` 應採用較新的 `summary.json.as_of` 判斷 stale，避免 UI 因狀態檔落後而誤判 blocked。
- 資料 stale 判斷使用交易日邏輯：預設排除週末，並可透過 `backend/data/trading_calendar.json` 設定 `holidays` 與 `makeup_trading_days`。本地日曆缺失或格式錯誤時退回週一至週五邏輯。
- 每次完整更新應產生 `backend/out/data_coverage_report.json`，列出追蹤股票覆蓋率、每檔 `ok` / `missing` / `insufficient` / `lagging` 狀態、原因、預期交易日與 raw OHLCV 最新日。覆蓋率低於 80% 時 Update Workflow / Daily Check 應視為交易輸出 blocked。
- `update_status.json`、`summary.json` 與 `data_coverage_report.json` 應共享同一個 `batch_id` / `lineage`，讓訊號可追溯到本次資料批次；手動 `run_signals.py` 也需產生 signal-only lineage。
- 每次 `run_signals.py` 應保存 `backend/out/signal_snapshots/signal_snapshot_YYYY-MM-DD.json`，並產生 `backend/out/signal_snapshot_review.json`；review 只比較前一份計畫與本次訊號的 action 變化，作為隔日復盤稽核，不得當成績效證明或新交易訊號。
- 每次 `run_signals.py` 應由 `signal_snapshot_review.json` 產生 `backend/out/signal_alerts.json`；alerts 只整理 `risk_triggered`、`action_changed`、`risk_eased`、`missing_current` 等變化，作為 Daily Check 待辦提示，不代表外部通知已送出。
- `summary.json`、`daily_brief.json`、signal snapshot、snapshot review 與 `signal_alerts.json` 都必須保留同一份 `rules_version` / `rules_metadata`，避免日後無法解釋舊輸出。
- `python3 scripts/today_scan.py` 是盤後規則掃描入口，只能讀取既有 `summary.json` / `daily_brief.json` / `universe_report.csv`，分出正式可小試、老王觀察、穩健動能與風險處理；不得重算策略、放寬濾網或新增推薦桶。
- `run_signals.py` 每次產生正式輸出時應同步刷新 `backend/out/today_scan.json`；每日更新流程的預期輸出也必須包含此檔，避免使用者看到舊掃描分桶。
- `today_scan.json` 是衍生報告，必須保留資料日、規則版本、大盤濾網與分桶原因；老王大盤濾網為 block 時，老王候選只能列觀察並顯示封鎖原因。
- 每次刷新 `today_scan.json` 時，應同步保存 `backend/out/today_scans/today_scan_YYYY-MM-DD.json`，供隔日驗算與歷史復盤；此快照同樣不得新增交易判斷。
- `summary.json`、`summary_previous.json`、`universe_report.csv`、`daily_brief.json`、`update_status.json` 與使用者資料 JSON 寫入時必須先寫同資料夾暫存檔，再 replace 正式檔，避免 API 讀到半寫入內容。
- 真實交易紀錄整批匯入前應先呼叫 `POST /api/trades/import/validate` 看完整錯誤清單，再呼叫 `POST /api/trades/import/preview` 確認匯入後持倉；正式覆蓋只能走 `POST /api/trades/import` 的 `replace` 流程，必須先驗證整批資料並備份舊 `trades.json`，不可直接覆蓋檔案。
- 交易匯入允許簡化格式；缺 `id` / `created_at` / `name` / 金額欄位時由 service 補齊，不要求使用者手動編 UUID 或建立時間。
- 交易匯入的 `warnings` 必須揭露自動補齊欄位的筆數，讓使用者匯入前能知道哪些資料不是原始提供。
- 清空交易紀錄只能走 `POST /api/trades/clear`，且 `confirm` 必須為 `CLEAR_TRADES`；清空前預設備份舊檔，匯入空清單不可視為清空。
- 交易備份只能從 `GET /api/trades/backups` 列出，還原只能走 `POST /api/trades/backups/restore` 並使用 `RESTORE_TRADES`；還原前必須先備份目前 `trades.json`。
- 個人資料整包備份只包含 `trades.json`、`decision_journal.json`、`watchlists.json`、`market_notes.json` 與 `settings.json`；不包含行情、fundamentals、chips、stock names 或 `backend/out/*` 產物。
- 個人資料還原必須先走 dry-run preview；正式還原只能使用 `confirm=RESTORE_PERSONAL_DATA`，且還原前必須自動建立 pre-restore backup。
- 必備欄位：`last_data_as_of`、`generated_at`、`universe_size`、`data_ok_count`、`data_missing_count`、`data_ok_pct`、`is_stale`、`stale_days`、`status_label`、`message`、`update_required`、`update_command`、`missing_stocks`、`files_written`。
- `is_stale=true` 時，作戰表仍可供回顧，但不應拿來做當日盤後決策；需先跑每日更新流程。
- `data_ok_pct` 低於 100% 時，必須搭配 `data_missing_count` 檢查哪些股票缺資料。
- `update_required=true` 時，應顯示 `update_command`，預設為 `python3 scripts/daily_update.py --months 1`。
- `missing_stocks` 最多列前 20 檔資料不足股票，需包含 `code`、`name`、`reason`。
- `python3 scripts/doctor.py` 是每日健康檢查入口；必須檢查 Python 套件、輸出檔日期同步、候選股資料完整率、基本面避雷覆蓋、基本面 priority CSV 狀態 / 可合併檔數 / 第一筆錯誤、候選股復盤缺口、候選股復盤 Markdown 草稿是否已產生與交易紀錄格式，並用 exit code `0/1/2` 表示 OK / WARN / BLOCK。
- doctor 報告的 `next_action` 應保留短版可讀指令；若是可執行命令，需補 `action_payload.kind=command`、`action_payload.command`、含 `cd backend` 的 `action_payload.copy_command` 與 `action_payload.expected_outputs`，不得只輸出 `cd backend && ...` 字串。
- `doctor.py` 若偵測 `fundamentals_report.priority_fill_readiness.status=ready_to_merge`，下一步應提示合併 priority CSV 並重算 signals；若 `status=invalid`，必須升級為 BLOCK 並顯示第一筆錯誤 / 警告，避免使用者只看到「基本面避雷 0/N」卻不知道卡在哪裡。
- `python3 scripts/daily_check.py` 是每日 PM 摘要入口，只能讀取 `doctor.py` 的報告並整理資料日、交易輸出是否可用與 Top N 待辦；除 `--write-report` 可寫出 `backend/out/daily_check.json` 外，不得自行更新資料、建立決策日誌、合併 fundamentals 或改寫任何 out/data 檔。
- `daily_check.json.signal_alerts` 應保留本次 `signal_alerts.json` 摘要；只有 `alert_count > 0` 時才加入 Top actions，且只加入一筆 `signal_alerts` action，避免重複轟炸。
- `daily_check.json.today_scan` 應保留本次 `today_scan.json` 摘要；只有交易輸出可用時，才可把今日規則掃描加入 Top actions，避免資料阻塞時把舊候選包裝成今日建議。
- `python3 scripts/update_all_data.py`、`python3 scripts/run_signals.py` 與 API 背景更新完成後應嘗試刷新 `backend/out/daily_check.json`，但 daily check 寫入失敗不得覆蓋原本資料更新或訊號計算結果。
- `GET /api/system/daily-check` 只能讀取既有 `backend/out/daily_check.json`；若檔案不存在或格式錯誤，回傳 404 並提示先執行 `python3 scripts/daily_check.py --write-report`，不得在 router 內即時重算 daily check。
- Dashboard 顯示 `daily_brief` 時必須露出覆蓋率、缺資料數與前幾檔 `missing_stocks`；輪動清單與 `tomorrow_tasks` 的股票應可直接回到技術分析頁檢查線圖與進出場價。
- 候選股篩選報告也必須露出資料完整率、缺資料檔數、可進場 / 等回測 / 需處理風險等動作摘要；缺資料股票應能直接點回技術分析頁查看資料不足原因。
- 候選股篩選報告可在前端用既有欄位衍生「距進場區間 / 距停損 / 距停利目標」百分比，幫助掃描位置；此為顯示輔助，不得覆蓋 `entry_price_low/high`、`stop_price`、`target_price` 或 `price_plan_note`。
- 候選股篩選報告可提供價格位置篩選（進場區間內、低於進場區、高於進場區、有完整價格計畫），但只能使用既有收盤價與價格計畫欄位衍生，不得新增另一套買賣判斷。
- 候選股篩選報告排序可提供 `daily_priority`、`score`、`reward_risk_ratio`、距進場區與距目標等視角；預設必須仍為「今日優先」，避免分數排序蓋過風控優先順序。
- 候選股篩選報告可提供目前篩選結果摘要、Top 3 與下載目前結果 CSV，供盤後筆記或復盤使用；匯出與複製內容只能反映目前報表欄位與前端篩選，不應另算新訊號。
- 候選股篩選報告的摘要與匯出 CSV 應包含復盤進度 / 復盤狀態，讓盤後留存檔能追蹤哪些可行動股票已留下理由；此欄位只能由既有決策日誌來源判定。
- 候選股篩選報告可從目前報表列新增決策日誌，但必須走既有 `POST /api/decision-journal`，source 標記為 `universe_report`，且不得修改交易紀錄、持倉或現金。
- 候選股篩選報告應依資料日讀取既有決策日誌；同一資料日同一股票若已由報表建立紀錄，前端需顯示「已記錄」並避免重複新增。
- 候選股篩選報告可提供復盤狀態篩選；「尚未記錄」只應顯示可行動清單（可小試、等回測、減碼、出場）且尚未有 `source='universe_report'` 同資料日紀錄的股票。
- 候選股篩選報告列可顯示復盤狀態標籤；判斷必須與復盤狀態篩選一致，不得另建一套狀態規則。
- 候選股篩選報告的今日優先清單必須跟隨目前表格篩選範圍，包含復盤狀態、價格位置、關鍵字與今日動作篩選，避免上下區塊出現不同股票集合。
- 候選股篩選報告可顯示復盤進度卡，統計目前前端篩選範圍內的可行動清單、已記錄、尚未記錄與全部報表紀錄數；此統計只讀既有報表與決策日誌，不得新增交易判斷。
- 候選股篩選報告可複製待補復盤清單，內容只能包含目前篩選範圍內尚未有 `source='universe_report'` 紀錄的可行動股票、既有今日動作、關鍵價、失效條件與理由。
- 候選股篩選報告可在復盤進度區與今日優先清單顯示待補復盤股票捷徑，並提供顯示全部待補的篩選入口；記錄仍必須由使用者逐筆按下並走既有確認流程，不得批次自動建立。
- 候選股篩選報告在沒有待補復盤時應明確顯示「都已復盤」或「目前沒有可行動復盤股票」，並可提供查看已復盤 / 清除篩選入口，避免使用者誤以為資料未載入。
- 盤後需要完整待補復盤清單時，可執行 `python3 scripts/export_universe_review_todo.py` 產生 `backend/out/universe_report_review_todo.md`；此檔只作人工復盤草稿，不得自動建立決策日誌、交易紀錄或改寫訊號。
- Dashboard 應顯示 `GET /api/system/workflow-status` 的 PM 工作流狀態；若 `overall_status=blocked` 或 `running`，必須先處理 next_actions，不應把 stale / 缺報表狀態包裝成可交易訊號。
- `workflow-status.decision_guardrails` 是交易輸出可用性的最後閘門；資料過期、報表缺失或 `daily_brief` 標記需更新時，`can_use_trade_outputs=false`，Dashboard 必須明確顯示哪些輸出只能回顧、不可作為今天進出場依據。
- Dashboard 的 `next_actions` 可以提供導引按鈕，例如更新資料、補盤後筆記、補決策紀錄或重算訊號；導引按鈕只能導向既有區塊或觸發既有 API，不得新增另一套判斷。
- Dashboard 對 `action_type='universe_report'` 的導引只能切換到候選股篩選報告頁，讓使用者從報表列建立 `source='universe_report'` 的決策日誌；不得自動替使用者建立紀錄。
- Dashboard 導向候選股復盤時可預設開啟報表的「尚未記錄」篩選，讓使用者直接處理缺口；此導覽不得改變任何訊號或交易輸出。
- Dashboard 可顯示候選股待補復盤 Top 3，但資料必須來自 `workflow-status.checks.universe_report_journal.missing_actionable_items`，前端不得重新計算候選股復盤缺口；排序需先處理出場、減碼，再處理可小試與等回測。
- Dashboard 可複製候選股待補復盤清單，但內容只能取自 `workflow-status.checks.universe_report_journal.missing_actionable_items` 的代碼、名稱、今日動作、關鍵價、失效條件與理由；複製不得建立決策日誌或改變報表篩選。
- 需要使用者執行指令的 `next_actions` 應提供 `success_check` 與 `expected_outputs`，讓 Dashboard 能顯示跑完後要檢查的檔案與驗收條件。
- `workflow-status.readiness_review` 是每日資料閉環總表，固定彙整資料日、交易報表、人工盤後筆記、基本面避雷資料與持股決策紀錄；若有 blocked，`top_blocker_key` 必須指向第一個應處理的區塊。
- `workflow-status` 應追蹤候選股報表可行動清單（可小試、等回測、減碼、出場）的決策日誌覆蓋率；僅計入 `source='universe_report'` 的同資料日紀錄，避免手動筆記誤判為報表復盤完成。
- Dashboard 顯示基本面避雷狀態時，應優先使用 `GET /api/system/fundamentals-status` 的 `next_fill_targets`、`field_missing_counts` 與覆蓋率；只能呈現缺資料摘要，不得用前端補算長期價值訊號。
- `fundamentals-status.priority_fill_readiness` 是補資料 CSV 的操作閘門；`invalid` 時不可預覽或合併，`empty` 時可預覽但不可正式合併，`ready_to_preview` 才能進入正式合併確認流程。
- `doctor.py` / `daily_check.json` 的基本面待辦必須保留 `workflow_stage`、`workflow_headline`、`workflow_primary_action` 與 `workflow_checklist`；Daily Check 顯示 WARN 時，應能直接說明目前是產生 CSV、填寫 CSV、預覽合併或重跑 signals 的哪一步。
- `GET /api/system/fundamentals-priority-fill` 只提供 `fundamentals_priority_fill.csv` 下載，內容由 fundamental service 依現有缺資料狀態產生；不得在 router 內組 CSV 或計算欄位。
- `POST /api/system/fundamentals-priority-fill/merge` 可預覽或合併優先補資料 CSV；正式合併必須提供確認字串，並由 service 合併 `fundamentals.csv` 後匯入 `fundamentals.json`。
- `workflow-status.close_checklist` 固定包含收盤流程六步：更新資料、補盤後筆記、重算訊號、檢查每日作戰表、檢查候選股報告、檢查持股風險；狀態只能是 `done` / `todo` / `blocked` / `running`。
- `workflow-status.portfolio_tasks` 只能從 `universe_report.csv` 的目前持股列整理，使用既有 `daily_action`、`daily_key_price`、`daily_invalidation` 與 `daily_priority`；不得在 workflow service 另建一套持股買賣判斷。
- `workflow-status.workflow_metrics` 是 PM KPI，只能由 `next_actions`、`close_checklist` 與 `portfolio_tasks` 推導，供 Dashboard 第一眼呈現阻塞、提醒、流程完成度與持股風險數。
- 決策日誌 `backend/data/decision_journal.json` 只記錄「當下為什麼買 / 賣 / 續抱 / 觀察 / 不進場」，不能修改持倉、現金或 `trades.json`。
- 新增決策日誌時必須用原子寫入，且同步存下當下 `workflow-status.overall_status` 與 `workflow-status.headline`，讓日後復盤能看出決策是在資料就緒、警告或阻塞狀態下做出的。
- 決策日誌允許的 `decision` 只有 `buy` / `sell` / `hold` / `skip` / `reduce` / `watch`；必須有日期、代號、名稱與理由。
- Dashboard 可以從 `workflow-status.portfolio_tasks` 帶入決策日誌草稿，但只能複製既有 action、reason、key_price、invalidation，不得在前端另算新的買賣判斷。
- Dashboard 從持股待辦帶入決策日誌時，日期必須優先使用 `workflow-status.data_as_of`，避免資料日與系統今天不同而造成 PM KPI 不更新；使用者仍可手動改日期。
- Dashboard 決策日誌列表預設篩選 `workflow-status.data_as_of`，並可手動切換日期、`decision` 與股票代號；列表篩選只影響復盤檢視，不改變 PM KPI 或交易判斷。
- Dashboard 決策日誌區可集中顯示 `workflow-status.portfolio_tasks` 中尚未記錄的持股待辦；可以提供「看線圖」與「帶入草稿」，但不得自動替使用者儲存決策。
- Dashboard 決策日誌列表可提供「線圖」入口與已填寫的價格、數量、關鍵價、失效條件摘要，供復盤對照；這些顯示不得改寫原始日誌內容。
- `workflow-status.workflow_metrics` 必須揭露 `decision_journal_today_count` 與 `portfolio_tasks_without_journal_count`，用 `data_as_of` 對齊今天持股待辦是否已留下決策紀錄。
- `workflow-status.portfolio_tasks[*].journal_recorded` 只表示該持股待辦在 `data_as_of` 是否已有決策日誌，不代表交易已執行；Dashboard 可用它顯示「已記錄 / 待記錄」。
- 刪除決策日誌只能刪 `decision_journal.json` 中指定 id 的復盤紀錄，不得影響 `trades.json`、持倉、現金或任何訊號輸出。
- 編輯決策日誌只能修改復盤內容本身，必須保留原本 `id`、`created_at` 與建立時的 `workflow_status` / `workflow_headline`，並寫入 `updated_at`，避免改寫當下決策情境。
- 決策日誌 summary 只能統計指定日期的復盤紀錄數與 decision 分布，不得由此推論新的買賣訊號或改寫 PM 工作流判斷。

每日汰弱留強輸出：

- `daily_brief.rotation_plan.continue_hold`：續抱觀察，只放 `daily_action=hold` 或正式 `hold` 訊號；策略共振只影響排序與說明，不把等回測標的改列續抱。
- `daily_brief.rotation_plan.wait_pullback`：等回測，只放 `daily_action=wait_pullback`；不因 `watchlist` 或 `no_alignment` 自動歸入此桶。
- `daily_brief.rotation_plan.entry_candidates`：可進場或準備入場，但仍需看失效條件與風險報酬。
- `daily_brief.rotation_plan.priority_reduce`：優先減碼 / 出場處理，包含出場警示、失效與策略衝突。
- `daily_brief.rotation_plan.avoid_no_chase`：暫不碰或不追高，放 `daily_action=avoid` 或 `take_profit_warning`，包含過熱、風險報酬不足或資料不足。
- 分類必須互斥，優先順序為 `priority_reduce` > `entry_candidates` > `continue_hold` > `wait_pullback` > `avoid_no_chase`。
- `priority_reduce` 優先級高於續抱與共振；若內部技術訊號已轉風險，不得因老王 / 基本面避雷成立而改列續抱。

隔日任務表：

- `daily_brief.tomorrow_tasks`：將每檔股票整理成隔日可執行任務，不新增策略，只結構化既有 `daily_action` 與價格計畫。
- 每筆任務至少包含 `bucket`、`trigger_action`、`watch_price`、`entry_plan`、`stop_plan`、`exit_plan`、`invalidation`、`reason`。
- `bucket` 必須與每日汰弱留強分類同邏輯；若是長期基本面觀察但沒有短線買點，可列 `long_watch`。
- `watch_price` 優先使用 `daily_key_price`；`entry_plan` 使用 `entry_price_low/high`，沒有進場區時明確寫「不建議新進場」。
- `stop_plan` 與 `invalidation` 用來回答「跌破哪裡要處理」；`exit_plan` 用 `target_price` 或壓力區回答「出場 / 停利看哪裡」。

---

## 9) 進出場價格規則

必備欄位：

- `entry_price_low`
- `entry_price_high`
- `stop_price`
- `target_price`
- `risk_pct`
- `reward_pct`
- `reward_risk_ratio`
- `price_plan_note`
- `support_source`
- `resistance_source`
- `entry_source`
- `stop_source`
- `target_source`

解讀：

- 進場區間以 MA20、支撐區、回測區或突破區估算。
- 停損以支撐、爆大量低點、均線或型態失效位置估算。
- 停利以壓力區、前高或型態目標估算。
- 停利區 / RSI 過熱 / R/R 不足時，`entry_price_low/high` 可以為空，避免暗示可追價。
- 來源欄位必須跟實際價格算法一致；若價格為空，來源欄位也應為空字串。

---

## 10) 工作前檢查

每次改策略、訊號、分析頁、候選股表、Dashboard 盤後筆記前，先讀：

1. `backend/docs/current_rules.md`
2. `backend/docs/signal_rules.md`
3. 若修改資料輸入 / 輸出，再看 `backend/docs/api.md` 與 `backend/docs/operations.md`

若規則與程式不一致，先更新規則或明確說明本次要調整哪一條規則，再改實作。
