"""Application startup configuration."""

import logging
import os
from collections.abc import Mapping


DEFAULT_CORS_ALLOWED_ORIGINS = ("http://localhost:5173",)

log = logging.getLogger(__name__)


def resolve_cors_allowed_origins(
    env: Mapping[str, str] | None = None,
) -> list[str]:
    source = os.environ if env is None else env
    raw = source.get("CORS_ALLOWED_ORIGINS", "")
    origins = list(
        dict.fromkeys(item.strip() for item in raw.split(",") if item.strip())
    )
    if not origins:
        return list(DEFAULT_CORS_ALLOWED_ORIGINS)
    if any("*" in origin for origin in origins):
        log.warning(
            "CORS_ALLOWED_ORIGINS cannot contain wildcard; using localhost default"
        )
        return list(DEFAULT_CORS_ALLOWED_ORIGINS)
    return origins
