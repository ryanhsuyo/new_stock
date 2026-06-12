from app.storage.settings_store import load_trading_settings


def get_trading_settings() -> dict[str, float]:
    return load_trading_settings()
