"""验收用例 C1 ~ C10 + 本组补充 T-S1 / T-S2。

每条测试对应 SRS分析.md 第 5 节的一行。测试函数名显式标注用例编号，
方便实验报告直接引用 pytest 输出。
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 必须在 import main 之前注入
_TEST_DB = Path(tempfile.gettempdir()) / f"campus_accept_{os.getpid()}.sqlite3"
os.environ["CAMPUS_EVENT_DB"] = str(_TEST_DB)

from project.api import deps as _deps  # noqa: E402
from project.db import reset_db  # noqa: E402
from project.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolation():
    reset_db(_TEST_DB)
    for fn_name in ("get_activity_repository", "get_registration_repository", "get_message_repository"):
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


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _create_activity(client, *, capacity: int, policy: str, title: str = "活动") -> str:
    r = client.post("/api/admin/activities", json={
        "title": title,
        "category": "测试",
        "start_at": _future(),
        "location": "X",
        "capacity": capacity,
        "policy_type": policy,
    })
    assert r.status_code == 201, r.text
    return r.json()["activity_id"]


def _register(client, activity_id: str, student_id: str):
    return client.post(f"/api/activities/{activity_id}/registrations",
                       json={"student_id": student_id})


def _wait():
    """在同步事件总线场景下无实际作用，占位便于异步时接入。"""
    import time; time.sleep(0)


# ===========================================================================
# C1 —— 管理员创建直接报名活动，容量 2；创建成功，可供学生报名。
# ===========================================================================

def test_C1_create_direct_activity(client):
    aid = _create_activity(client, capacity=2, policy="DIRECT", title="直接活动")
    r = client.get(f"/api/activities/{aid}")
    assert r.status_code == 200
    assert r.json()["capacity"] == 2
    assert r.json()["policy_type"] == "DIRECT"
    assert r.json()["remaining_seats"] == 2


# ===========================================================================
# C2 —— 学生 A 报名直接报名活动，直接变为"已通过"并生成通知。
# ===========================================================================

def test_C2_direct_registration_auto_approved_with_notice(client):
    aid = _create_activity(client, capacity=5, policy="DIRECT", title="直接活动")

    r = _register(client, aid, "S001")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "APPROVED"
    reg_id = r.json()["registration_id"]

    # 剩余名额减 1
    assert client.get(f"/api/activities/{aid}").json()["remaining_seats"] == 4

    # 通知已落库
    msgs = client.get("/api/students/S001/messages").json()
    assert any("已通过" in m["content"] for m in msgs), f"未找到通过通知：{msgs}"
    # 我的报名
    mine = client.get("/api/students/S001/registrations").json()
    assert any(x["registration_id"] == reg_id for x in mine)


# ===========================================================================
# C3 —— 学生 A 再次提交相同活动报名；拒绝重复有效报名。
# ===========================================================================

def test_C3_duplicate_registration_rejected(client):
    aid = _create_activity(client, capacity=5, policy="DIRECT", title="直接活动")
    # 第一次报名：成功 → APPROVED
    assert _register(client, aid, "S001").status_code == 201
    # 第二次：必须 400，且不能产生第二条有效报名记录
    r = _register(client, aid, "S001")
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "DUPLICATE_REGISTRATION"
    mine = client.get("/api/students/S001/registrations").json()
    # 历史只有一条
    assert len(mine) == 1


# ===========================================================================
# C4 —— 学生 A 报名（占名额），B 报名（也占名额），C 报名失败。
# （容量 2，DIRECT）
# ===========================================================================

def test_C4_direct_registration_capacity_enforced(client):
    aid = _create_activity(client, capacity=2, policy="DIRECT", title="满员活动")
    # A / B 分别占一个名额
    assert _register(client, aid, "S001").json()["status"] == "APPROVED"
    assert _register(client, aid, "S002").json()["status"] == "APPROVED"
    # C 必须拒绝
    r = _register(client, aid, "S003")
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "CAPACITY_EXCEEDED"
    # remaining_seats = 0
    assert client.get(f"/api/activities/{aid}").json()["remaining_seats"] == 0


# ===========================================================================
# C5 —— 审核型活动，学生 A 申请；状态为"待审核"。
# ===========================================================================

def test_C5_approval_registration_initial_pending(client):
    aid = _create_activity(client, capacity=2, policy="APPROVAL", title="审核活动")
    r = _register(client, aid, "S001")
    assert r.status_code == 201
    assert r.json()["status"] == "PENDING"
    # PENDING 不占名额（B.2.3）
    assert client.get(f"/api/activities/{aid}").json()["remaining_seats"] == 2
    # 已生成"等待审核"通知
    msgs = client.get("/api/students/S001/messages").json()
    assert any("等待" in m["content"] for m in msgs), f"未找到等待审核通知：{msgs}"


# ===========================================================================
# C6 —— 管理员批准 A 的待审核报名；变为"已通过"且生成通知。
# ===========================================================================

def test_C6_admin_approve_pending(client):
    aid = _create_activity(client, capacity=2, policy="APPROVAL", title="审核活动")
    reg_id = _register(client, aid, "S001").json()["registration_id"]

    r = client.post(f"/api/admin/registrations/{reg_id}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    # approved_count = 1，remaining = 1
    stats = client.get(f"/api/admin/activities/{aid}/stats").json()
    assert stats["approved_count"] == 1
    assert stats["remaining_seats"] == 1
    # 审核结果通知已生成
    msgs = client.get("/api/students/S001/messages").json()
    assert any("已通过" in m["content"] for m in msgs)


# ===========================================================================
# C7 —— 管理员拒绝另一待审核报名；变为"已拒绝"且生成通知。
# ===========================================================================

def test_C7_admin_reject_pending(client):
    aid = _create_activity(client, capacity=2, policy="APPROVAL", title="审核活动")
    reg_id = _register(client, aid, "S001").json()["registration_id"]

    r = client.post(f"/api/admin/registrations/{reg_id}/reject")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"
    # 已拒绝不占名额
    stats = client.get(f"/api/admin/activities/{aid}/stats").json()
    assert stats["approved_count"] == 0
    assert stats["remaining_seats"] == 2
    # 已拒绝通知
    msgs = client.get("/api/students/S001/messages").json()
    assert any("已拒绝" in m["content"] for m in msgs)


# ===========================================================================
# C8 —— 批准操作时容量已满；批准失败，报名保持"待审核"，人数不超上限。
# ===========================================================================

def test_C8_approve_blocked_when_full(client):
    aid = _create_activity(client, capacity=1, policy="APPROVAL", title="满员审核")
    # A 先报 → PENDING；B 也报 → PENDING（都不占名额）
    regA = _register(client, aid, "S001").json()["registration_id"]
    regB = _register(client, aid, "S002").json()["registration_id"]

    # 批准 A → approved_count=1，remaining=0
    client.post(f"/api/admin/registrations/{regA}/approve")

    # 再批准 B → 必须失败，regB 保持 PENDING，approved_count 还是 1
    r = client.post(f"/api/admin/registrations/{regB}/approve")
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "CAPACITY_EXCEEDED"
    stats = client.get(f"/api/admin/activities/{aid}/stats").json()
    assert stats["approved_count"] == 1  # 不能超
    # B 的报名状态仍为 PENDING
    mineB = client.get("/api/students/S002/registrations").json()
    assert any(x["registration_id"] == regB and x["status"] == "PENDING" for x in mineB)


# ===========================================================================
# C9 —— 学生取消待审核 / 已通过报名；状态"已取消"，统计同步变化。
# ===========================================================================

def test_C9_cancel_pending_and_approved(client):
    aid_dir = _create_activity(client, capacity=2, policy="DIRECT", title="直接取消")
    aid_aud = _create_activity(client, capacity=2, policy="APPROVAL", title="审核取消")

    # 场景 1：取消已通过报名 → 名额归还
    reg_direct = _register(client, aid_dir, "S001").json()["registration_id"]
    assert client.get(f"/api/activities/{aid_dir}").json()["remaining_seats"] == 1
    r = client.delete(f"/api/students/S001/registrations/{reg_direct}")
    assert r.status_code == 204
    assert client.get(f"/api/activities/{aid_dir}").json()["remaining_seats"] == 2

    # 场景 2：取消待审核报名
    reg_aud = _register(client, aid_aud, "S001").json()["registration_id"]
    r = client.delete(f"/api/students/S001/registrations/{reg_aud}")
    assert r.status_code == 204
    mine = client.get("/api/students/S001/registrations").json()
    assert all(x["status"] == "CANCELLED" for x in mine)


# ===========================================================================
# C10 —— 数据持久化：服务重启后查询活动、报名、通知，数据仍一致。
# ===========================================================================

def test_C10_persistence_after_restart():
    # 第一次应用生命周期：写入活动、报名和通知，随后完全关闭客户端。
    with TestClient(app) as first_client:
        aid = _create_activity(first_client, capacity=5, policy="DIRECT", title="持久化活动")
        reg_id = _register(first_client, aid, "S001").json()["registration_id"]

    # 第二次应用生命周期：重新触发启动钩子，通过 API 验证三类数据仍存在。
    with TestClient(app) as restarted_client:
        activity_response = restarted_client.get(f"/api/activities/{aid}")
        assert activity_response.status_code == 200
        assert activity_response.json()["title"] == "持久化活动"
        assert activity_response.json()["remaining_seats"] == 4

        registrations = restarted_client.get("/api/students/S001/registrations").json()
        assert any(
            item["registration_id"] == reg_id
            and item["activity_id"] == aid
            and item["status"] == "APPROVED"
            for item in registrations
        )

        messages = restarted_client.get("/api/students/S001/messages").json()
        assert any(
            item["activity_id"] == aid and "已通过" in item["content"]
            for item in messages
        )


# ===========================================================================
# T-S1 —— 本组补充：活动开始后仍允许取消报名。
# ===========================================================================

def test_T_S1_cancel_after_start_allowed(client):
    # 先创建未来活动 → 报名 → 手动把开始时间调到过去 → 取消
    aid = _create_activity(client, capacity=2, policy="DIRECT", title="后取消")
    reg_id = _register(client, aid, "S001").json()["registration_id"]

    past = (datetime.now() - timedelta(hours=1)).isoformat()
    client.put(f"/api/admin/activities/{aid}", json={"start_at": past})

    # 活动已开始，不能再报名（C1 反例）
    r = _register(client, aid, "S002")
    assert r.status_code == 400
    assert r.json()["code"] == "ACTIVITY_STARTED"

    # 但 T-S1 允许取消已通过报名
    r = client.delete(f"/api/students/S001/registrations/{reg_id}")
    assert r.status_code == 204
    # 名额归还
    assert client.get(f"/api/activities/{aid}").json()["remaining_seats"] == 2


# ===========================================================================
# T-S2 —— 本组补充：有任意历史报名记录即拒绝删除。
# ===========================================================================

def test_T_S2_delete_rejected_with_any_registration(client):
    # 先创建 → 报名 → 取消 → 再尝试删除（已取消的历史报名也应阻止）
    aid = _create_activity(client, capacity=2, policy="DIRECT", title="将被拒绝删除")
    reg_id = _register(client, aid, "S001").json()["registration_id"]
    client.delete(f"/api/students/S001/registrations/{reg_id}")

    # 此时 activities 表存在已取消历史报名 → 拒绝删除
    r = client.delete(f"/api/admin/activities/{aid}")
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "DELETE_REJECTED"
    # 活动还在
    assert client.get(f"/api/activities/{aid}").status_code == 200

    # 无报名记录的活动可以删
    aid2 = _create_activity(client, capacity=2, policy="DIRECT", title="可删活动")
    r = client.delete(f"/api/admin/activities/{aid2}")
    assert r.status_code == 204


# ===========================================================================
# 补充边界测试：名称筛选、历史记录后重新报名、通知失败、活动编辑。
# ===========================================================================

def test_boundary_activity_name_filter(client):
    marathon_id = _create_activity(client, capacity=5, policy="DIRECT", title="校园马拉松")
    _create_activity(client, capacity=5, policy="DIRECT", title="AI 创新讲座")

    response = client.get("/api/activities", params={"keyword": "马拉松"})
    assert response.status_code == 200
    activities = response.json()
    assert len(activities) == 1
    assert activities[0]["activity_id"] == marathon_id
    assert activities[0]["title"] == "校园马拉松"


def test_boundary_reregister_after_cancel_or_reject(client):
    direct_id = _create_activity(client, capacity=3, policy="DIRECT", title="取消后重报")
    cancelled_id = _register(client, direct_id, "S001").json()["registration_id"]
    assert client.delete(f"/api/students/S001/registrations/{cancelled_id}").status_code == 204

    direct_response = _register(client, direct_id, "S001")
    assert direct_response.status_code == 201
    assert direct_response.json()["status"] == "APPROVED"
    assert direct_response.json()["registration_id"] != cancelled_id

    approval_id = _create_activity(client, capacity=3, policy="APPROVAL", title="拒绝后重报")
    rejected_id = _register(client, approval_id, "S001").json()["registration_id"]
    assert client.post(f"/api/admin/registrations/{rejected_id}/reject").status_code == 200

    approval_response = _register(client, approval_id, "S001")
    assert approval_response.status_code == 201
    assert approval_response.json()["status"] == "PENDING"
    assert approval_response.json()["registration_id"] != rejected_id

    direct_history = [
        item for item in client.get("/api/students/S001/registrations").json()
        if item["activity_id"] == direct_id
    ]
    approval_history = [
        item for item in client.get("/api/students/S001/registrations").json()
        if item["activity_id"] == approval_id
    ]
    assert {item["status"] for item in direct_history} == {"CANCELLED", "APPROVED"}
    assert {item["status"] for item in approval_history} == {"REJECTED", "PENDING"}


def test_boundary_notification_failure_does_not_rollback_registration(
    client, monkeypatch, caplog
):
    import logging

    activity_id = _create_activity(client, capacity=2, policy="DIRECT", title="通知故障")
    notification_service = _deps.get_notification_service()

    def fail_save(_message):
        raise RuntimeError("模拟通知写库失败")

    monkeypatch.setattr(notification_service._message_repository, "save", fail_save)
    with caplog.at_level(logging.ERROR, logger="project.services.notification_service"):
        response = _register(client, activity_id, "S001")

    assert response.status_code == 201
    registration_id = response.json()["registration_id"]
    assert response.json()["status"] == "APPROVED"
    registrations = client.get("/api/students/S001/registrations").json()
    assert any(item["registration_id"] == registration_id for item in registrations)
    assert client.get("/api/students/S001/messages").json() == []
    assert "站内通知写入失败" in caplog.text


def test_boundary_activity_capacity_update_guard(client):
    activity_id = _create_activity(client, capacity=2, policy="DIRECT", title="容量调整")
    assert _register(client, activity_id, "S001").status_code == 201
    assert _register(client, activity_id, "S002").status_code == 201

    rejected = client.put(f"/api/admin/activities/{activity_id}", json={"capacity": 1})
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "CAPACITY_EXCEEDED"
    unchanged = client.get(f"/api/activities/{activity_id}").json()
    assert unchanged["capacity"] == 2
    assert unchanged["remaining_seats"] == 0

    updated = client.put(f"/api/admin/activities/{activity_id}", json={"capacity": 3})
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 3
    assert updated.json()["remaining_seats"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
