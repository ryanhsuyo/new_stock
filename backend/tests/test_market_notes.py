import json

import app.services.signals_service as svc


def test_market_note_marks_old_note_as_stale(tmp_path, monkeypatch):
    notes_path = tmp_path / "market_notes.json"
    notes_path.write_text(
        json.dumps([
            {
                "date": "2026-05-14",
                "title": "盤後風控筆記",
                "risk_level": "caution",
                "headline": "測試筆記",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "MARKET_NOTES_PATH", notes_path)

    note = svc._market_note_for_date("2026-05-19")

    assert note["date"] == "2026-05-14"
    assert note["applies_to_as_of"] == "2026-05-19"
    assert note["stale_trading_days"] == 3
    assert note["is_stale"] is True
    assert note["update_required"] is True
    assert note["status_label"] == "舊筆記"
    assert "距離訊號基準日 3 個交易日" in note["stale_reason"]


def test_market_note_keeps_recent_note_fresh(tmp_path, monkeypatch):
    notes_path = tmp_path / "market_notes.json"
    notes_path.write_text(
        json.dumps([
            {
                "date": "2026-05-19",
                "title": "盤後風控筆記",
                "risk_level": "caution",
                "headline": "測試筆記",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "MARKET_NOTES_PATH", notes_path)

    note = svc._market_note_for_date("2026-05-19")

    assert note["date"] == "2026-05-19"
    assert note["stale_trading_days"] == 0
    assert note["is_stale"] is False
    assert note["update_required"] is False
    assert note["status_label"] == "最新筆記"
    assert note["stale_reason"] == ""


def test_market_note_derives_playbook_from_manual_report(tmp_path, monkeypatch):
    notes_path = tmp_path / "market_notes.json"
    notes_path.write_text(
        json.dumps([
            {
                "date": "2026-05-27",
                "title": "盤後風控筆記：提高七成水位，突破前高後看 MA5 / MA10 續航",
                "risk_level": "strong",
                "source": "user_pasted_report",
                "headline": "短線資金持股操作建議：維持七成持股水位",
                "position_guidance": "短線資金提高到七成，但仍汰弱留強，不追沒有量價確認的高檔股。",
                "market_actions": [
                    "台股加權放量突破前高並創高，短線優先看 MA5，波段看 MA10。",
                    "記憶體、AI / 半導體、ABF / 載板、PCB / 散熱、被動元件與電源周邊優先觀察。",
                ],
                "index_notes": ["加權 2026-05-27 收 44680.67，櫃買同步創高。"],
                "stock_notes": [
                    "3481 群創、2344 華邦電、2408 南亞科、2337 旺宏、6770 力積電續抱觀察。",
                    "3006 晶豪科、2454 聯發科、3037 欣興、8046 南電看 MA5 / MA10 與前高壓力。",
                ],
                "rules": [
                    "出量續攻可續抱，量縮轉弱才降低追價與持股。",
                    "跌破爆大量低點、MA5 / MA10 或月線支撐才轉保守。",
                ],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "MARKET_NOTES_PATH", notes_path)

    note = svc._market_note_for_date("2026-05-27")

    playbook = note["playbook"]
    assert playbook["target_level"] == "七成"
    assert playbook["target_position_pct"] == 70
    assert playbook["stance"] == "risk_on"
    assert playbook["focus_sectors"][:3] == ["記憶體", "AI / 半導體", "ABF / 載板"]
    assert "量縮轉弱" in playbook["risk_controls"][0]
    assert {"3481", "2344", "6770", "8046"}.issubset(set(playbook["watch_codes"]))
    assert "2026" not in playbook["watch_codes"]
    assert "44680" not in playbook["watch_codes"]
