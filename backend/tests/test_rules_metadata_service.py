import json


def test_rules_metadata_schema_is_stable_and_serializable():
    from app.services.rules_metadata_service import RULES_VERSION, build_rules_metadata

    metadata = build_rules_metadata()

    assert metadata["version"] == RULES_VERSION
    assert metadata["strategy_profile"] == "two_strategy_daily_v1"
    assert metadata["generated_by"] == "rules_metadata_service"
    assert metadata["parameters"]["MIN_ROWS"] == 60
    assert metadata["parameters"]["SR_LOOKBACK"] == 20
    assert metadata["parameters"]["RSI_PERIOD"] == 14
    assert metadata["parameters"]["OLD_WANG_MA10_TOLERANCE_PCT"] == 0.002
    assert metadata["strategies"]["old_wang"]["id"] == "old_wang_market_chip_rotation"
    assert metadata["strategies"]["steady_momentum"]["id"] == "steady_momentum_v1"
    json.dumps(metadata, ensure_ascii=False)
