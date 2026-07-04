from app.services.signals_service import _strategy_alignment


def test_strategy_alignment_marks_core_old_wang_steady_momentum_alignment():
    result = _strategy_alignment(
        internal_signal="ready_to_enter",
        old_wang_flag=True,
        steady_momentum_flag=True,
    )

    assert result["strategy_alignment"] == "strong_alignment"
    assert result["aligned_strategies"] == ["old_wang", "steady_momentum"]
    assert result["strategy_conflict_notes"] == []


def test_strategy_alignment_never_exposes_internal_core_as_product_strategy():
    product_strategies = {"old_wang", "steady_momentum"}

    for internal_signal in ("entry_confirmed", "ready_to_enter", "hold", "watchlist"):
        result = _strategy_alignment(
            internal_signal=internal_signal,
            old_wang_flag=True,
            steady_momentum_flag=True,
        )

        assert set(result["aligned_strategies"]).issubset(product_strategies)


def test_strategy_alignment_marks_core_risk_conflict():
    result = _strategy_alignment(
        internal_signal="exit_warning",
        old_wang_flag=True,
        steady_momentum_flag=True,
    )

    assert result["strategy_alignment"] == "conflict"
    assert result["aligned_strategies"] == ["old_wang", "steady_momentum"]
    assert "內部技術訊號已轉風險" in result["strategy_conflict_notes"][0]


def test_strategy_alignment_marks_single_old_wang_without_core_confirmation():
    result = _strategy_alignment(
        internal_signal="watchlist",
        old_wang_flag=True,
        steady_momentum_flag=False,
    )

    assert result["strategy_alignment"] == "single_strategy"
    assert result["aligned_strategies"] == ["old_wang"]
    assert "日線買點尚未確認" in result["strategy_conflict_notes"][0]
