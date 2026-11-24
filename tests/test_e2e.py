"""健康检查冒烟 + 模块导入验证（最早一轮 E2E，现已由 acceptance 全覆盖）。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DB = Path(tempfile.gettempdir()) / f"campus_e2e_{os.getpid()}.sqlite3"
os.environ["CAMPUS_EVENT_DB"] = str(_TEST_DB)

from project.db import reset_db  # noqa: E402
from project.main import app  # noqa: E402
from project.api import deps as _deps  # noqa: E402


@pytest.fixture(autouse=True)
def isolation():
    reset_db(_TEST_DB)
    for fn_name in ("get_activity_repository", "get_registration_repository", "get_message_repository"):
        fn = getattr(_deps, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["app"] == "CampusEvent"
