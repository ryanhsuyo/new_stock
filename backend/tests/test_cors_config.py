import logging

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import DEFAULT_CORS_ALLOWED_ORIGINS, resolve_cors_allowed_origins


def test_missing_cors_origins_use_localhost_default():
    assert resolve_cors_allowed_origins({}) == list(DEFAULT_CORS_ALLOWED_ORIGINS)


def test_blank_cors_origins_use_localhost_default():
    assert resolve_cors_allowed_origins(
        {"CORS_ALLOWED_ORIGINS": " ,  , "}
    ) == list(DEFAULT_CORS_ALLOWED_ORIGINS)


def test_cors_origins_are_trimmed_and_deduplicated():
    result = resolve_cors_allowed_origins(
        {
            "CORS_ALLOWED_ORIGINS": (
                "https://a.example, https://b.example,https://a.example"
            )
        }
    )

    assert result == ["https://a.example", "https://b.example"]


def test_wildcard_cors_origin_falls_back_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        result = resolve_cors_allowed_origins(
            {"CORS_ALLOWED_ORIGINS": "https://a.example,*"}
        )

    assert result == list(DEFAULT_CORS_ALLOWED_ORIGINS)
    assert "wildcard" in caplog.text


def test_wildcard_inside_cors_origin_is_rejected(caplog):
    with caplog.at_level(logging.WARNING):
        result = resolve_cors_allowed_origins(
            {"CORS_ALLOWED_ORIGINS": "https://*.example.com"}
        )

    assert result == list(DEFAULT_CORS_ALLOWED_ORIGINS)
    assert "wildcard" in caplog.text


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/stocks/universe",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_configured_origin_passes_real_app_preflight():
    client = TestClient(main_module.create_app(["https://stock.example.com"]))

    response = _preflight(client, "https://stock.example.com")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://stock.example.com"
    )


def test_unconfigured_origin_is_not_allowed_by_real_app():
    client = TestClient(main_module.create_app(["https://stock.example.com"]))

    response = _preflight(client, "https://blocked.example.com")

    assert "access-control-allow-origin" not in response.headers
