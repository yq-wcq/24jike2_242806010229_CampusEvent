"""CR-02 验收：模拟邮件通知（教师材料验收表 CR2-01 ~ CR2-05）。"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DB = Path(tempfile.gettempdir()) / f"campus_cr02_{os.getpid()}.sqlite3"
os.environ["CAMPUS_EVENT_DB"] = str(_TEST_DB)

from project.api import deps as _deps  # noqa: E402
from project.config import settings  # noqa: E402
from project.db import reset_db  # noqa: E402
from project.domain.enums import RegistrationStatus  # noqa: E402
from project.domain.events import RegistrationStatusChangedEvent  # noqa: E402
from project.main import app  # noqa: E402
from project.services.email_service import EmailNotificationService  # noqa: E402


class FailingEmailSender:
    def send(self, *, recipient: str, subject: str, content: str) -> None:
        raise RuntimeError("模拟邮件服务不可用")


@pytest.fixture(autouse=True)
def isolation():
    reset_db(settings.database_path)
    for fn_name in (
        "get_activity_repository",
        "get_registration_repository",
        "get_message_repository",
        "get_student_repository",
        "get_email_log_repository",
        "get_email_sender",
        "get_email_service",
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


def _create_activity(client, *, capacity: int = 5, policy: str = "DIRECT") -> str:
    r = client.post("/api/admin/activities", json={
        "title": "邮件测试活动",
        "category": "测试",
        "start_at": _future(),
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


def _emails(client) -> list[dict]:
    r = client.get("/api/admin/email-logs")
    assert r.status_code == 200, r.text
    return r.json()


def test_cr2_01_direct_registration_creates_message_and_email(client) -> None:
    activity_id = _create_activity(client)
    r = _register(client, activity_id, "S001")
    assert r.status_code == 201

    messages = client.get("/api/students/S001/messages").json()
    assert len(messages) == 1

    emails = _emails(client)
    assert len(emails) == 1
    assert emails[0]["status"] == "SENT"
    assert emails[0]["recipient"] == "s001@campus.example"
    assert "已通过" in emails[0]["subject"]
    assert emails[0]["registration_id"] == r.json()["registration_id"]


def test_cr2_02_approve_and_reject_record_both_channels(client) -> None:
    activity_id = _create_activity(client, policy="APPROVAL")

    reg_a = _register(client, activity_id, "S001").json()
    assert _emails(client) == []  # PENDING 只发站内消息
    approved = client.post(f"/api/admin/registrations/{reg_a['registration_id']}/approve")
    assert approved.status_code == 200

    reg_b = _register(client, activity_id, "S002").json()
    rejected = client.post(f"/api/admin/registrations/{reg_b['registration_id']}/reject")
    assert rejected.status_code == 200

    emails = _emails(client)
    assert len(emails) == 2
    assert all(item["status"] == "SENT" for item in emails)
    subjects = {item["registration_id"]: item["subject"] for item in emails}
    assert "已通过" in subjects[reg_a["registration_id"]]
    assert "未通过" in subjects[reg_b["registration_id"]]

    assert len(client.get("/api/students/S001/messages").json()) == 2
    assert len(client.get("/api/students/S002/messages").json()) == 2


def test_cr2_03_email_failure_keeps_registration_and_logs_error(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    reg = _register(client, activity_id, "S002")
    assert reg.status_code == 201

    failing_service = EmailNotificationService(
        student_repository=_deps.get_student_repository(),
        email_log_repository=_deps.get_email_log_repository(),
        sender=FailingEmailSender(),
    )
    event = RegistrationStatusChangedEvent(
        registration_id=reg.json()["registration_id"],
        student_id="S002",
        activity_id=activity_id,
        from_status=None,
        to_status=RegistrationStatus.APPROVED,
    )
    failing_service.on_event(event)  # 不得向上抛出

    mine = client.get("/api/students/S002/registrations").json()
    assert mine[0]["status"] == "APPROVED"

    emails = _emails(client)
    failed = [item for item in emails if item["status"] == "FAILED"]
    assert len(failed) == 1
    assert "模拟邮件服务不可用" in failed[0]["error"]


def test_cr2_04_duplicate_event_and_duplicate_action_send_once(client) -> None:
    activity_id = _create_activity(client, capacity=2)
    reg = _register(client, activity_id, "S001")
    assert reg.status_code == 201
    emails = _emails(client)
    assert len(emails) == 1
    event_id = emails[0]["event_id"]

    # 同一事件重复投递：唯一约束与存在性检查双重去重
    duplicate_event = RegistrationStatusChangedEvent(
        registration_id=reg.json()["registration_id"],
        student_id="S001",
        activity_id=activity_id,
        from_status=None,
        to_status=RegistrationStatus.APPROVED,
        event_id=event_id,
    )
    _deps.get_email_service().on_event(duplicate_event)
    assert len(_emails(client)) == 1

    # 同一业务动作重复提交被公共规则拒绝，也不应产生新邮件
    again = _register(client, activity_id, "S001")
    assert again.status_code == 400
    assert len(_emails(client)) == 1


def test_cr2_05_pending_does_not_send_email(client) -> None:
    activity_id = _create_activity(client, policy="APPROVAL")
    assert _register(client, activity_id, "S003").status_code == 201
    assert len(client.get("/api/students/S003/messages").json()) == 1
    assert _emails(client) == []
