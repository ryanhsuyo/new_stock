# us_trend_follow 逐日回放驗證報告（2026-06-15 ～ 2026-06-30）

> **evaluation-only**：非推薦、非買賣建議、不下單；production 策略規則零改動、無參數最佳化。
> 產生：2026-07-11。重現：`cd backend && python3.11 scripts/replay_us_strategy.py`
> 完整結果：`backend/out/us_strategy_replay_2026-06-15_2026-06-30.{json,csv}`（gitignored，重跑即得）。

## 方法

- **Walk-forward**：對每個交易日 D，指標（MA20/MA60/RSI14/20 日漲跌幅/dist_ma20）一律由 `date <= D` 的切片重算（`_build_asof_item` 只吃前綴切片），有測試證明竄改 D 之後的資料不影響 as-of D 的結果。候選條件直接呼叫 production `classify_trend_follow`（不複製規則）。
- **成交時點**：D 收盤成為 candidate → D+1 交易日 **open** 進場；無下一 open → unresolved（不用 D 收盤假裝成交）。
- **兩套 evaluation-only 退出**（觸發後下一交易日 open 出）：
  - A `candidate_exit`：第一次不再符合 candidate。
  - B `trend_protect_exit`：gate 轉 inactive／close < MA60／連續 2 日 close < MA20。overheated 不觸發退出；無停損停利；無參數調整。
- 訊號區間 6/15–6/30（11 個交易日），退出觀察到資料最後日 **2026-07-10**。

## 每日候選變化（gate 全程 bullish，未關門）

| 日期 | candidates | 變動 |
|---|---|---|
| 06-15 | KO, PG, TSM | — |
| 06-16 | AMD, ASML, PG, TSM | +AMD,ASML −KO |
| 06-17 | PG, TSM | −AMD,ASML |
| 06-18 | AMD, PG | +AMD −TSM |
| 06-22 | PG | −AMD |
| 06-23 | ASML | +ASML −PG |
| 06-24 | KO, TSM | +KO,TSM −ASML |
| 06-25 | AMD, ASML, PG | +AMD,ASML,PG −KO,TSM |
| 06-26 | AMD, ASML, KO, PG, SNOW | +KO,SNOW |
| 06-29 | AMD, ASML, KO, PG, TSM | +TSM −SNOW |
| 06-30 | TSLA | +TSLA −AMD,ASML,KO,PG,TSM |

churn：11 天中 **10 天有進出**，累計新增 13、移除 15。移除原因統計：**dist>8%（防追高）6 次**、**RSI<50 5 次**、跌破 MA20 3 次、20 日漲跌幅轉負 3 次、RSI>68 1 次。

## 兩套退出法比較

| 指標 | A. candidate_exit | B. trend_protect_exit |
|---|---|---|
| signals | 16 | 8 |
| completed / unresolved | 16 / 0 | 6 / 2（至 7/10 仍持有：KO、SNOW） |
| win rate | 56.2% | 33.3% |
| avg / median return | +0.68% / +0.34% | −2.29% / −1.75% |
| best / worst | +9.19%（TSM）/ −6.68%（AMD） | +2.46%（TSM）/ −8.44%（ASML） |
| 平均持有（交易日） | **1.9** | 9.3 |
| avg MFE / MAE | +3.92% / −3.38% | +4.98% / −5.88% |
| 3 日內再入選 | **8 次** | 1 次 |
| exit reasons | not_candidate ×16 | below_MA20×2d ×5、below_MA60 ×1、open_at_data_end ×2 |

## 問題證據（依 spec 逐題回答）

1. **有產生候選**：11 天皆有 1–5 檔；7 檔曾入選（KO、PG、TSM、AMD、ASML、SNOW、TSLA）、16 個訊號。
2. **進場明細**：見 CSV；例：TSM 6/15 訊號 → 6/16 open 436.02 進場。
3. **candidate_exit 太敏感 — 證據成立**：平均持有 1.9 天、16 筆中 8 筆 3 日內再入選、11 天中 10 天清單變動。根因是**入選邊界被對稱地當退出用**：
   - `dist>8%` 移除 6 次 —— 股票**因為漲太快**被踢出（AMD 6/30 dist +12.3%），對「進場觀察」合理、對「退出」語意錯誤。
   - `RSI<50` 移除 5 次 —— RSI 在 50 附近震盪（AMD 49.1、KO 49.7、TSM 47.4）。
   - 極限案例：ASML 6/24 收 1762.77 vs MA20 1763.22（差 0.03%）被移除。
4. **trend_protect 結構較合理**：只在趨勢受損時出場（MA20×2 日／MA60／gate），持有 9.3 天、再入選僅 1 次。本窗口報酬較差（−2.29%，ASML −8.44% 貢獻大）是**持有穿越 7 月初回檔**的結果；6 筆完成樣本無法評價報酬優劣，但語意一致性明顯優於 A。
5. **頻繁剛退出又入選 — 是**：A 規則 8 次（如 AMD 6/17 出→6/18 進）。
6. **gate 是否不合理關門 — 本窗口無法評估**：11 天全 bullish、零關門。gate 邏輯未被壓力測試——這是**資料窗口限制，不是策略問題**。
7. **邊界是否卡太緊**：作為**入場**條件，證據不支持「太緊」（每天仍有 1–5 檔）；抖動主因是邊界被 candidate_exit 重複用作退出。RSI 50 下緣與 dist 8% 上緣是抖動熱點（合計 11/15 次移除）。
8. **建議（先提證據、不改規則）**：
   - 若未來要正式 entry/exit contract：**不要用 candidate_exit**；以 trend_protect 型（結構受損）為基礎。
   - 若在意觀察清單 UI 穩定度：考慮**遲滯（hysteresis）**——退出門檻比入選鬆（例：入選 RSI≥50、除名 RSI<45），需更長樣本驗證後另案。
   - 「因強勢離開清單」（dist>8）與「因轉弱離開」語意不同，前端可考慮區分顯示；規則本身不必改。
9. **資料不足 vs 策略問題**：27 檔資料完整（各 256 筆、窗口內零 no_data 排除）→ 上述抖動是**策略邊界特性**，非資料問題。反之 gate 未測（bullish 全程）與樣本僅 11 天/16 筆 → 報酬統計**只能看方向**。

## 限制（必讀）

- Yahoo Finance 非官方資料源，價格未經第二來源核對。
- 未計股息、滑價、手續費；以日線 open 模擬成交，跳空日偏差可能大。
- 交易日曆 = 資料出現的日期，無 NYSE 完整假日曆。
- 訊號窗僅 11 個交易日、樣本極小；win rate / 平均報酬不可外推。
- Walk-forward 只保證不用未來**價格**；策略規則本身以近期行情設計，規則層後見之明無法排除。

## 結論

us_trend_follow 作為**觀察清單**可用（每天有候選、每筆有理由、gate 誠實），但 `candidate_exit` 語意證實不適合當退出邏輯（抖動由入場邊界的對稱重用造成）；若要演進為正式 entry/exit contract，應以 trend_protect 型為基底並另案設計遲滯，**本輪不改任何 production 規則**。
