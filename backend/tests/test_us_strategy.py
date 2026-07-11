"""
test_us_strategy.py — 美股觀察策略 us_trend_follow（大盤守門的趨勢延續）。

以受控 analysis item（純函式）驗規則邊界；以 monkeypatch get_us_analysis 驗
gate / 排序 / contract；以 TestClient 驗 endpoint schema。不打真網路。
**策略為觀察用：非推薦、非買賣建議、非下單。**
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import us_strategy_service as st

client = TestClient(app)

VALID_STATES = {"candidate", "watch", "avoid", "overheated"}


def _item(**kw) -> dict:
    """合成 analysis item：預設為一檔標準 candidate（全部入選條件通過）。"""
    base = dict(
        code="AAA", name="Alpha Corp.", category="Mega-cap Tech", region="US",
        data_status="ok", row_count=200, last_data_as_of="2026-07-10",
        last_close=110.0, ma20=105.0, ma60=100.0, rsi14=60.0,
        change_20d_pct=5.0, dist_ma20_pct=4.76, dist_ma60_pct=10.0,
        days_since_last=0, status="trend_up", status_label="趨勢向上",
    )
    base.update(kw)
    return base


def _benchmark(code: str, above: bool) -> dict:
    """SPY/QQQ 基準 item：above 控制 close 相對 MA60。"""
    return _item(
        code=code, name=code, category="ETF / Benchmark",
        last_close=110.0 if above else 90.0, ma20=105.0 if above else 95.0, ma60=100.0,
        status="trend_up" if above else "weak",
    )


# ── classify_trend_follow：規則邊界（純函式）─────────────────────────────────

def test_candidate_passes_all_conditions():
    r = st.classify_trend_follow(_item(), "bullish")
    assert r["bucket"] == "candidate" and r["state"] == "candidate"
    assert r["reasons"] and r["risk_notes"]          # candidate 必有 reasons + risk_notes


def test_rsi_boundary_68_in_70_overheated():
    assert st.classify_trend_follow(_item(rsi14=68.0), "bullish")["bucket"] == "candidate"
    r69 = st.classify_trend_follow(_item(rsi14=69.0), "bullish")
    assert r69["bucket"] == "excluded" and r69["state"] == "watch"   # 68–70 之間：防追高、非過熱
    r70 = st.classify_trend_follow(_item(rsi14=70.0), "bullish")
    assert r70["state"] == "overheated"


def test_rsi_below_50_excluded():
    r = st.classify_trend_follow(_item(rsi14=49.0), "bullish")
    assert r["bucket"] == "excluded" and r["state"] == "watch"
    assert any("動能不足" in x for x in r["reasons"])


def test_dist_boundary_8_in_15_overheated():
    assert st.classify_trend_follow(_item(dist_ma20_pct=8.0), "bullish")["bucket"] == "candidate"
    r10 = st.classify_trend_follow(_item(dist_ma20_pct=10.0), "bullish")
    assert r10["bucket"] == "excluded" and r10["state"] == "watch"
    assert any("防追高" in x for x in r10["reasons"])
    r15 = st.classify_trend_follow(_item(dist_ma20_pct=15.0), "bullish")
    assert r15["state"] == "overheated"


def test_etf_benchmark_never_candidate():
    r = st.classify_trend_follow(_benchmark("SPY", above=True), "bullish")
    assert r["bucket"] == "excluded"
    assert any("量尺" in x for x in r["reasons"])


def test_below_ma60_is_avoid():
    r = st.classify_trend_follow(_item(last_close=95.0, dist_ma20_pct=-9.5, status="weak"), "bullish")
    assert r["state"] == "avoid"
    assert any("MA60" in x for x in r["reasons"])


def test_recovering_is_watch_not_candidate():
    r = st.classify_trend_follow(
        _item(ma20=98.0, ma60=100.0, last_close=105.0, dist_ma20_pct=7.1, status="recovering"),
        "bullish",
    )
    assert r["bucket"] == "excluded" and r["state"] == "watch"
    assert any("修復中" in x for x in r["reasons"])


def test_no_data_is_avoid():
    r = st.classify_trend_follow(
        _item(row_count=0, last_close=None, ma20=None, ma60=None, rsi14=None,
              dist_ma20_pct=None, change_20d_pct=None, status="no_data"),
        "bullish",
    )
    assert r["state"] == "avoid"
    assert any("資料不足" in x for x in r["reasons"])


def test_negative_20d_change_excluded():
    r = st.classify_trend_follow(_item(change_20d_pct=-1.0), "bullish")
    assert r["bucket"] == "excluded"
    assert any("近月未走升" in x for x in r["reasons"])


def test_mixed_bias_downgrades_candidate_to_watch():
    r = st.classify_trend_follow(_item(), "mixed")
    assert r["bucket"] == "candidate" and r["state"] == "watch"
    assert any("大盤分歧" in x for x in r["reasons"])


# ── get_us_trend_follow：gate / 排序 / contract ──────────────────────────────

def _fake_universe(bench_above: tuple[bool, bool]) -> list[dict]:
    """SPY/QQQ 控制 bias + 三檔個股：兩檔 candidate（dist 不同）、一檔 weak。"""
    spy_up, qqq_up = bench_above
    return [
        _benchmark("SPY", spy_up),
        _benchmark("QQQ", qqq_up),
        _item(code="AAA", dist_ma20_pct=5.0, change_20d_pct=4.0),
        _item(code="BBB", dist_ma20_pct=2.0, change_20d_pct=3.0),
        _item(code="CCC", last_close=95.0, dist_ma20_pct=-9.5, status="weak"),
    ]


def test_bearish_gate_closes_with_note(monkeypatch):
    monkeypatch.setattr(st, "get_us_analysis", lambda: _fake_universe((False, False)))
    out = st.get_us_trend_follow()
    assert out["strategy"] == "us_trend_follow"
    assert out["market_gate"]["active"] is False
    assert out["market_gate"]["bias"] == "bearish"
    assert out["market_gate"]["note"] == "大盤在 MA60 下方或資料不足，本策略今日不產生觀察對象"
    assert out["candidates"] == []
    # 原本符合條件者移入 excluded，且說明是守門關閉
    gated = [e for e in out["excluded"] if "守門關閉" in "".join(e["reasons"])]
    assert {e["code"] for e in gated} == {"AAA", "BBB"}
    assert all(e["state"] == "watch" for e in gated)


def test_bullish_gate_candidates_sorted_and_ranked(monkeypatch):
    monkeypatch.setattr(st, "get_us_analysis", lambda: _fake_universe((True, True)))
    out = st.get_us_trend_follow()
    assert out["market_gate"]["active"] is True and out["market_gate"]["bias"] == "bullish"
    codes = [c["code"] for c in out["candidates"]]
    assert codes == ["BBB", "AAA"]                    # dist 2.0 < 5.0
    assert [c["rank"] for c in out["candidates"]] == [1, 2]
    for c in out["candidates"]:
        assert c["state"] == "candidate"
        assert c["reasons"] and c["risk_notes"]       # 必有 reasons + risk_notes
    # ETF 與 weak 都在 excluded，各有 reasons
    exc = {e["code"]: e for e in out["excluded"]}
    assert set(exc) == {"SPY", "QQQ", "CCC"}
    assert all(e["reasons"] for e in exc.values())
    assert exc["CCC"]["state"] == "avoid"


def test_sort_tiebreak_by_change_then_code(monkeypatch):
    rows = [
        _benchmark("SPY", True), _benchmark("QQQ", True),
        _item(code="DDD", dist_ma20_pct=3.0, change_20d_pct=2.0),
        _item(code="EEE", dist_ma20_pct=3.0, change_20d_pct=6.0),
        _item(code="FFF", dist_ma20_pct=3.0, change_20d_pct=6.0),
    ]
    monkeypatch.setattr(st, "get_us_analysis", lambda: rows)
    out = st.get_us_trend_follow()
    assert [c["code"] for c in out["candidates"]] == ["EEE", "FFF", "DDD"]


def test_mixed_gate_active_but_watch(monkeypatch):
    monkeypatch.setattr(st, "get_us_analysis", lambda: _fake_universe((True, False)))
    out = st.get_us_trend_follow()
    assert out["market_gate"]["active"] is True and out["market_gate"]["bias"] == "mixed"
    assert len(out["candidates"]) == 2
    for c in out["candidates"]:
        assert c["state"] == "watch"
        assert any("大盤分歧" in x for x in c["reasons"])


def test_no_scores_anywhere(monkeypatch):
    monkeypatch.setattr(st, "get_us_analysis", lambda: _fake_universe((True, True)))
    out = st.get_us_trend_follow()
    for c in out["candidates"]:
        assert "score" not in c                        # 只有 rank，不做 0–100 分數


# ── HTTP 端點 schema ─────────────────────────────────────────────────────────

def test_trend_follow_endpoint_schema():
    res = client.get("/api/markets/us/strategy/trend-follow")
    assert res.status_code == 200
    body = res.json()
    assert body["strategy"] == "us_trend_follow"
    assert body["strategy_label"]
    gate = body["market_gate"]
    assert isinstance(gate["active"], bool)
    assert gate["bias"] in {"bullish", "bearish", "mixed", "unknown"}
    assert gate["note"]
    assert isinstance(body["candidates"], list) and isinstance(body["excluded"], list)
    for c in body["candidates"]:
        for key in ("code", "name", "category", "close", "state", "rank",
                    "reasons", "risk_notes", "data_as_of"):
            assert key in c
        assert c["state"] in VALID_STATES
        assert c["reasons"] and c["risk_notes"]
    for e in body["excluded"]:
        for key in ("code", "name", "category", "close", "state", "reasons", "data_as_of"):
            assert key in e
        assert e["state"] in VALID_STATES
        assert e["reasons"]
    # gate 關閉時 candidates 必為空（規則，非故障）
    if not gate["active"]:
        assert body["candidates"] == []
