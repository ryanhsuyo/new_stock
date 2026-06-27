"""
pytest 設定：
  - 把 backend/ 加入 sys.path，讓 `from app.xxx import` 正常運作
  - 提供 client fixture（FastAPI TestClient）
  - 提供 tmp_out fixture：將 signals_service._OUT 與 router._OUT 導向暫存目錄，
    避免測試污染 backend/out/
"""

import sys
import time
from pathlib import Path

# backend/ 目錄
_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def tmp_out(tmp_path, monkeypatch):
    """
    把 signals_service._OUT 與 router stocks._OUT 都導向 tmp_path/out，
    讓每個測試從乾淨狀態出發。
    """
    import app.services.daily_brief_service as brief_svc
    import app.services.signals_service as svc
    import app.routers.stocks as router

    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(svc, "_OUT", out)
    monkeypatch.setattr(brief_svc, "_OUT", out)
    monkeypatch.setattr(router, "_OUT", out)
    yield out

    deadline = time.monotonic() + 30
    while (
        svc._signals_run_status.get("status") == "running"
        and svc._signals_lock.locked()
    ):
        if time.monotonic() >= deadline:
            pytest.fail("background signal run did not finish during fixture teardown")
        time.sleep(0.01)
