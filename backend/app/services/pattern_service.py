"""
pattern_service.py — W底 / M頂 / 頭肩底 / 頭肩頂型態辨識（第一版）

辨識規則
--------
W底 (w_bottom)：
  1. 找最近兩個「相近」擺盪低點（差距 ≤ SIMILARITY_TOL = 5%）
  2. 兩低點之間的最高 high（頸線）須高於兩低點至少 NECKLINE_MIN = 3%
  3. status 判斷：
     - confirmed ：收盤 ≥ 頸線 × (1 - CONFIRM_TOL)，即站上或接近頸線
     - failed    ：收盤 ＜ 兩低點最低 × (1 - FAIL_TOL)，即有效跌破底部
     - forming   ：其餘（底部完成、頸線尚未突破）

M頂 (m_top)：
  1. 找最近兩個「相近」擺盪高點（差距 ≤ SIMILARITY_TOL = 5%）
  2. 兩高點之間的最低 low（頸線）須低於兩高點至少 NECKLINE_MIN = 3%
  3. status 判斷：
     - confirmed ：收盤 ≤ 頸線 × (1 + CONFIRM_TOL)，即跌至或接近頸線
     - failed    ：收盤 ＞ 兩高點最高 × (1 + FAIL_TOL)，即有效突破頂部
     - forming   ：其餘（頂部完成、頸線尚未跌破）

頭肩底 (head_and_shoulders_bottom)：
  1. 找最近三個擺盪低點，第二個低點為頭且明顯低於左右肩
  2. 左右肩差距需在 _SHOULDER_TOL 內，避免形狀過度失衡
  3. 頸線 = 左肩到頭、頭到右肩兩段高點的較高者
  4. status 判斷：
     - confirmed ：收盤 ≥ 頸線 × (1 - CONFIRM_TOL)
     - failed    ：收盤 ＜ 頭部低點 × (1 - FAIL_TOL)
     - forming   ：其餘（右肩完成、頸線尚未突破）

頭肩頂 (head_and_shoulders_top)：
  1. 找最近三個擺盪高點，第二個高點為頭且明顯高於左右肩
  2. 左右肩差距需在 _SHOULDER_TOL 內
  3. 頸線 = 左肩到頭、頭到右肩兩段低點的較低者
  4. status 判斷：confirmed 跌破頸線、failed 突破頭部、其餘 forming

優先順序（多種都偵測到時）：以最後錨點日期較新者優先；同日期時 W底、頭肩底、頭肩頂、M頂。

注意：swing 偵測內部限定 rows[-120:]，pattern 配對最多往前查 MAX_PAIR_GAP = 3 個擺盪點。

公開介面
--------
    detect_pattern(rows: list[dict], window: int = 5) -> PatternResult
"""

from app.models.analysis import PatternResult

# ── 參數（明確記錄以便後續調整）─────────────────────────────────────────────
_SIMILARITY_TOL = 0.05   # 兩端點差距容忍：5%
_NECKLINE_MIN   = 0.03   # 頸線距端點最小落差：3%
_CONFIRM_TOL    = 0.01   # 突破 / 跌破的寬鬆量：1%（稍微未到頸線也算）
_FAIL_TOL       = 0.03   # 有效失效跌破量：3%
_MAX_PAIR_GAP   = 3      # 往前最多看幾個擺盪點（防止配對到太舊的點）
_SHOULDER_TOL   = 0.10   # 頭肩底左右肩差距容忍：10%
_HEAD_MIN_DROP  = 0.03   # 頭部需比左右肩至少低 3%
_HEAD_MIN_RISE  = 0.03   # 頭部需比左右肩至少高 3%


# ---------------------------------------------------------------------------
# 擺盪點偵測（獨立實作，避免 circular import with analysis_service）
# ---------------------------------------------------------------------------

def _swing_lows(rows: list[dict], window: int = 5) -> list[dict]:
    """偵測擺盪低點（rows[-120:] 範圍內）。"""
    data  = rows[-120:]
    lows  = [r["low"]  for r in data]
    dates = [r["date"] for r in data]
    result: list[dict] = []
    for i in range(window, len(lows) - window):
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            result.append({"date": dates[i], "price": lows[i]})
    return result


def _swing_highs(rows: list[dict], window: int = 5) -> list[dict]:
    """偵測擺盪高點（rows[-120:] 範圍內）。"""
    data  = rows[-120:]
    highs = [r["high"] for r in data]
    dates = [r["date"] for r in data]
    result: list[dict] = []
    for i in range(window, len(highs) - window):
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            result.append({"date": dates[i], "price": highs[i]})
    return result


def _date_idx(rows: list[dict], date: str) -> int:
    """找日期在 rows 中的索引，找不到回傳 -1。"""
    for i, r in enumerate(rows):
        if r["date"] == date:
            return i
    return -1


# ---------------------------------------------------------------------------
# W底偵測
# ---------------------------------------------------------------------------

def _detect_w_bottom(rows: list[dict], window: int = 5) -> dict:
    """
    回傳 dict：
      found=False → 未偵測到
      found=True  → p1, p2, neckline, status, note
    """
    swings = _swing_lows(rows, window)
    if len(swings) < 2:
        return {"found": False}

    close = rows[-1]["close"]

    for i in range(len(swings) - 1, 0, -1):
        p2 = swings[i]
        for j in range(i - 1, max(i - _MAX_PAIR_GAP - 1, -1), -1):
            p1 = swings[j]

            # 兩低點差距不超過 SIMILARITY_TOL
            if abs(p1["price"] - p2["price"]) / p1["price"] > _SIMILARITY_TOL:
                continue

            idx1 = _date_idx(rows, p1["date"])
            idx2 = _date_idx(rows, p2["date"])
            if idx1 < 0 or idx2 <= idx1:
                continue

            # 頸線 = 兩低點之間的最高 high
            between = rows[idx1 : idx2 + 1]
            neckline = round(max(r["high"] for r in between), 2)
            lower_low = round(min(p1["price"], p2["price"]), 2)

            # 頸線必須比兩低點高出至少 NECKLINE_MIN（排除假 W）
            if neckline < lower_low * (1 + _NECKLINE_MIN):
                continue

            # 判斷狀態
            if close < lower_low * (1 - _FAIL_TOL):
                status = "failed"
                note = f"W底失效：收盤 {close} 跌破底部 {lower_low}（跌破 {_FAIL_TOL*100:.0f}%）"
            elif close >= neckline * (1 - _CONFIRM_TOL):
                status = "confirmed"
                note = f"W底確認：收盤 {close} 突破頸線 {neckline}"
            else:
                status = "forming"
                note = f"W底形成中：兩底 {lower_low}，頸線 {neckline}，待突破確認"

            return {
                "found": True,
                "p1": p1, "p2": p2,
                "neckline": neckline,
                "status": status,
                "note": note,
            }

    return {"found": False}


# ---------------------------------------------------------------------------
# M頂偵測
# ---------------------------------------------------------------------------

def _detect_m_top(rows: list[dict], window: int = 5) -> dict:
    """
    回傳 dict：
      found=False → 未偵測到
      found=True  → p1, p2, neckline, status, note
    """
    swings = _swing_highs(rows, window)
    if len(swings) < 2:
        return {"found": False}

    close = rows[-1]["close"]

    for i in range(len(swings) - 1, 0, -1):
        p2 = swings[i]
        for j in range(i - 1, max(i - _MAX_PAIR_GAP - 1, -1), -1):
            p1 = swings[j]

            # 兩高點差距不超過 SIMILARITY_TOL
            if abs(p1["price"] - p2["price"]) / p1["price"] > _SIMILARITY_TOL:
                continue

            idx1 = _date_idx(rows, p1["date"])
            idx2 = _date_idx(rows, p2["date"])
            if idx1 < 0 or idx2 <= idx1:
                continue

            # 頸線 = 兩高點之間的最低 low
            between = rows[idx1 : idx2 + 1]
            neckline = round(min(r["low"] for r in between), 2)
            upper_high = round(max(p1["price"], p2["price"]), 2)

            # 頸線必須比兩高點低至少 NECKLINE_MIN（排除假 M）
            if neckline > upper_high * (1 - _NECKLINE_MIN):
                continue

            # 判斷狀態
            if close > upper_high * (1 + _FAIL_TOL):
                status = "failed"
                note = f"M頂失效：收盤 {close} 突破頂部 {upper_high}（突破 {_FAIL_TOL*100:.0f}%）"
            elif close <= neckline * (1 + _CONFIRM_TOL):
                status = "confirmed"
                note = f"M頂確認：收盤 {close} 跌破頸線 {neckline}"
            else:
                status = "forming"
                note = f"M頂形成中：兩頂 {upper_high}，頸線 {neckline}，注意跌破"

            return {
                "found": True,
                "p1": p1, "p2": p2,
                "neckline": neckline,
                "status": status,
                "note": note,
            }

    return {"found": False}


# ---------------------------------------------------------------------------
# 頭肩底偵測
# ---------------------------------------------------------------------------

def _detect_head_and_shoulders_bottom(rows: list[dict], window: int = 5) -> dict:
    """
    回傳 dict：
      found=False → 未偵測到
      found=True  → p1(左肩), p2(頭), p3(右肩), neckline, status, note
    """
    swings = _swing_lows(rows, window)
    if len(swings) < 3:
        return {"found": False}

    close = rows[-1]["close"]

    for i in range(len(swings) - 1, 1, -1):
        right = swings[i]
        for h in range(i - 1, max(i - _MAX_PAIR_GAP - 1, 0), -1):
            head = swings[h]
            for l in range(h - 1, max(h - _MAX_PAIR_GAP - 1, -1), -1):
                left = swings[l]

                left_price = left["price"]
                head_price = head["price"]
                right_price = right["price"]
                shoulder_base = (left_price + right_price) / 2

                if shoulder_base <= 0:
                    continue

                # 左右肩需大致相近，且頭部明顯更低。
                if abs(left_price - right_price) / shoulder_base > _SHOULDER_TOL:
                    continue
                if head_price >= min(left_price, right_price) * (1 - _HEAD_MIN_DROP):
                    continue

                idx_left = _date_idx(rows, left["date"])
                idx_head = _date_idx(rows, head["date"])
                idx_right = _date_idx(rows, right["date"])
                if idx_left < 0 or idx_head <= idx_left or idx_right <= idx_head:
                    continue

                left_peak = max(r["high"] for r in rows[idx_left:idx_head + 1])
                right_peak = max(r["high"] for r in rows[idx_head:idx_right + 1])
                neckline = round(max(left_peak, right_peak), 2)
                head_low = round(head_price, 2)
                shoulder_low = round(min(left_price, right_price), 2)

                if neckline < shoulder_low * (1 + _NECKLINE_MIN):
                    continue

                if close < head_low * (1 - _FAIL_TOL):
                    status = "failed"
                    note = f"頭肩底失效：收盤 {close} 跌破頭部低點 {head_low}（跌破 {_FAIL_TOL*100:.0f}%）"
                elif close >= neckline * (1 - _CONFIRM_TOL):
                    status = "confirmed"
                    note = f"頭肩底確認：收盤 {close} 突破頸線 {neckline}"
                else:
                    status = "forming"
                    note = f"頭肩底形成中：頭部 {head_low}，頸線 {neckline}，待突破確認"

                return {
                    "found": True,
                    "p1": left, "p2": head, "p3": right,
                    "neckline": neckline,
                    "status": status,
                    "note": note,
                }

    return {"found": False}


# ---------------------------------------------------------------------------
# 頭肩頂偵測
# ---------------------------------------------------------------------------

def _detect_head_and_shoulders_top(rows: list[dict], window: int = 5) -> dict:
    swings = _swing_highs(rows, window)
    if len(swings) < 3:
        return {"found": False}

    close = rows[-1]["close"]

    for i in range(len(swings) - 1, 1, -1):
        right = swings[i]
        for h in range(i - 1, max(i - _MAX_PAIR_GAP - 1, 0), -1):
            head = swings[h]
            for l in range(h - 1, max(h - _MAX_PAIR_GAP - 1, -1), -1):
                left = swings[l]
                shoulder_base = (left["price"] + right["price"]) / 2

                if shoulder_base <= 0:
                    continue
                if abs(left["price"] - right["price"]) / shoulder_base > _SHOULDER_TOL:
                    continue
                if head["price"] <= max(left["price"], right["price"]) * (1 + _HEAD_MIN_RISE):
                    continue

                idx_left = _date_idx(rows, left["date"])
                idx_head = _date_idx(rows, head["date"])
                idx_right = _date_idx(rows, right["date"])
                if idx_left < 0 or idx_head <= idx_left or idx_right <= idx_head:
                    continue

                left_trough = min(r["low"] for r in rows[idx_left:idx_head + 1])
                right_trough = min(r["low"] for r in rows[idx_head:idx_right + 1])
                neckline = round(min(left_trough, right_trough), 2)
                head_high = round(head["price"], 2)
                shoulder_high = round(min(left["price"], right["price"]), 2)

                if neckline > shoulder_high * (1 - _NECKLINE_MIN):
                    continue

                if close > head_high * (1 + _FAIL_TOL):
                    status = "failed"
                    note = f"頭肩頂失效：收盤 {close} 突破頭部高點 {head_high}（突破 {_FAIL_TOL*100:.0f}%）"
                elif close <= neckline * (1 + _CONFIRM_TOL):
                    status = "confirmed"
                    note = f"頭肩頂確認：收盤 {close} 跌破頸線 {neckline}"
                else:
                    status = "forming"
                    note = f"頭肩頂形成中：頭部 {head_high}，頸線 {neckline}，注意跌破"

                return {
                    "found": True,
                    "p1": left, "p2": head, "p3": right,
                    "neckline": neckline,
                    "status": status,
                    "note": note,
                }

    return {"found": False}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def detect_pattern(rows: list[dict], window: int = 5) -> PatternResult:
    """
    偵測最近一個型態（W底 / M頂 / 頭肩底 / 頭肩頂 / 無型態）。

    若多種都偵測到，以最後錨點日期較新者優先；同日期依序為
    W底、頭肩底、頭肩頂、M頂。
    """
    _NONE = PatternResult(
        pattern_type="none",
        pattern_status="none",
        neckline=None,
        note="未偵測到 W底、M頂、頭肩底或頭肩頂型態",
    )

    if len(rows) < 20:   # 太少資料直接回傳 none
        return PatternResult(
            pattern_type="none",
            pattern_status="none",
            neckline=None,
            note="資料不足，無法進行型態辨識",
        )

    w = _detect_w_bottom(rows, window)
    m = _detect_m_top(rows, window)
    hsb = _detect_head_and_shoulders_bottom(rows, window)
    hst = _detect_head_and_shoulders_top(rows, window)

    candidates = []
    if w["found"]:
        candidates.append(("w_bottom", w, w["p2"]["date"], 0))
    if hsb["found"]:
        candidates.append(("head_and_shoulders_bottom", hsb, hsb["p3"]["date"], 1))
    if hst["found"]:
        candidates.append(("head_and_shoulders_top", hst, hst["p3"]["date"], 2))
    if m["found"]:
        candidates.append(("m_top", m, m["p2"]["date"], 3))

    if not candidates:
        return _NONE

    pattern_type, data, _, _ = sorted(
        candidates, key=lambda item: (item[2], -item[3]), reverse=True
    )[0]
    return PatternResult(
        pattern_type=pattern_type,
        pattern_status=data["status"],
        neckline=data["neckline"],
        note=data["note"],
    )
