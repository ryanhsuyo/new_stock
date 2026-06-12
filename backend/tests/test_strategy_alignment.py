from app.services.signals_service import _strategy_alignment


def test_strategy_alignment_marks_core_old_wang_buffett_alignment():
    result = _strategy_alignment(
        internal_signal="ready_to_enter",
        old_wang_flag=True,
        buffett_flag=True,
    )

    assert result["strategy_alignment"] == "strong_alignment"
    assert result["aligned_strategies"] == ["core", "old_wang", "buffett"]
    assert result["strategy_conflict_notes"] == []


def test_strategy_alignment_marks_core_risk_conflict():
    result = _strategy_alignment(
        internal_signal="exit_warning",
        old_wang_flag=True,
        buffett_flag=True,
    )

    assert result["strategy_alignment"] == "conflict"
    assert result["aligned_strategies"] == ["old_wang", "buffett"]
    assert "核心技術已轉風險" in result["strategy_conflict_notes"][0]


def test_strategy_alignment_marks_single_old_wang_without_core_confirmation():
    result = _strategy_alignment(
        internal_signal="watchlist",
        old_wang_flag=True,
        buffett_flag=False,
    )

    assert result["strategy_alignment"] == "single_strategy"
    assert result["aligned_strategies"] == ["old_wang"]
    assert "核心尚未確認買點" in result["strategy_conflict_notes"][0]
