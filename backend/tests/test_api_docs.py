"""
test_api_docs.py — 防止 docs/api.md 與實際路由漂移

規則：app 中每一條 /api 路由的路徑字串，都必須出現在 docs/api.md 中
（至少要列在「端點索引」表）。新增 endpoint 時同步補文件，本測試才會過。
"""

from pathlib import Path

from app.main import app

DOCS_API = Path(__file__).resolve().parent.parent / "docs" / "api.md"


def _api_routes() -> list[tuple[str, str]]:
    routes = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or not path.startswith("/api"):
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            routes.add((method, path))
    return sorted(routes)


def test_api_docs_file_exists():
    assert DOCS_API.exists(), f"缺少 API 文件：{DOCS_API}"


def test_every_route_documented():
    doc = DOCS_API.read_text(encoding="utf-8")
    missing = [f"{method} {path}" for method, path in _api_routes() if path not in doc]
    assert not missing, (
        "以下路由未出現在 docs/api.md（請補進「端點索引」表）：\n  "
        + "\n  ".join(missing)
    )
