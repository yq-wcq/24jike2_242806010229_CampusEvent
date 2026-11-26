"""CR-01 验收：年级限定直接报名（教师材料验收表 CR1-01 ~ CR1-05）。"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DB = Path(tempfile.gettempdir()) / f"campus_cr01_{os.getpid()}.sqlite3"
os.environ["CAMPUS_EVENT_DB"] = str(_TEST_DB)

from project.api import deps as _deps  # noqa: E402
from project.config import settings  # noqa: E402
from project.db import reset_db  # noqa: E402
from project.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolation():
    reset_db(settings.database_path)
    for fn_name in (
        "get_activity_repository",
        "get_registration_repository",
        "get_message_repository",
        "get_student_repository",
    ):
        fn = getattr(_deps, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
    bus = _deps.get_event_bus()
    for listener in bus._listeners:
        if hasattr(listener, "_processed_event_ids"):
            listener._processed_event_ids.clear()
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _future(hours: int = 24) -> str:
    return (datetime.now() + timedelta(hours=hours)).isoformat()


def _create_activity(client, *, capacity: int, policy: str = "GRADE_DIRECT",
                     start_at: str | None = None) -> str:
    r = client.post("/api/admin/activities", json={
        "title": "年级限定活动",
        "category": "测试",
        "start_at": start_at or _future(),
        "location": "X",
        "capacity": capacity,
        "policy_type": policy,
    })
    assert r.status_code == 201, r.text
    return r.json()["activity_id"]


def _register(client, activity_id: str, student_id: str):
    return client.post(
        f"/api/activities/{activity_id}/registrations",
        json={"student_id": student_id},
    )


def test_cr1_01_sophomore_can_register(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    r = _register(client, activity_id, "S001")  # 大二
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "APPROVED"


def test_cr1_02_junior_can_register(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    r = _register(client, activity_id, "S002")  # 大三
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "APPROVED"


def test_cr1_03_freshman_is_rejected_with_reason(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    r = _register(client, activity_id, "S003")  # 大一
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["code"] == "GRADE_NOT_ELIGIBLE"
    assert "大二" in body["message"]


def test_cr1_04_senior_is_rejected_with_reason(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    r = _register(client, activity_id, "S004")  # 大四
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "GRADE_NOT_ELIGIBLE"


def test_cr1_grade_rule_still_respects_capacity(client) -> None:
    """CR1-05 的公共约束：年级合格也要受名额限制。"""
    activity_id = _create_activity(client, capacity=1)
    assert _register(client, activity_id, "S001").status_code == 201
    r = _register(client, activity_id, "S002")
    assert r.status_code == 400
    assert r.json()["code"] == "CAPACITY_EXCEEDED"


def test_cr1_grade_rule_still_respects_duplicate_check(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    assert _register(client, activity_id, "S001").status_code == 201
    r = _register(client, activity_id, "S001")
    assert r.status_code == 400
    assert r.json()["code"] == "DUPLICATE_REGISTRATION"


def test_cr1_grade_rule_still_respects_start_time(client) -> None:
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    activity_id = _create_activity(client, capacity=2, start_at=past)
    r = _register(client, activity_id, "S001")
    assert r.status_code == 400
    assert r.json()["code"] == "ACTIVITY_STARTED"


def test_cr1_unknown_student_is_rejected(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    r = _register(client, activity_id, "S999")
    assert r.status_code == 400
    assert r.json()["code"] == "STUDENT_NOT_FOUND"


def test_cr1_original_policies_are_unchanged(client) -> None:
    direct_id = _create_activity(client, capacity=2, policy="DIRECT")
    audit_id = _create_activity(client, capacity=2, policy="APPROVAL")
    assert _register(client, direct_id, "S003").json()["status"] == "APPROVED"
    assert _register(client, audit_id, "S003").json()["status"] == "PENDING"
