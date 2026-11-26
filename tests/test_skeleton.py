"""骨架自检：策略、状态机、活动时间窗口。业务服务尚未实现，不在本文件测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from project.domain.enums import PolicyType, RegistrationStatus
from project.domain.errors import InvalidTransitionError
from project.domain.models import Activity, Registration, Student
from project.policies.base import RegistrationContext
from project.policies.factory import RegistrationPolicyFactory


def make_registration(status: RegistrationStatus) -> Registration:
    now = datetime.now()
    return Registration("R1", "A1", "S001", status, now, now)


def make_context(grade: int = 2) -> RegistrationContext:
    return RegistrationContext(
        student=Student("S001", "张三", grade, "s001@campus.example"),
        activity=Activity(
            activity_id="A1",
            title="测试活动",
            category="讲座",
            start_at=datetime.now() + timedelta(hours=1),
            location="教学楼",
            capacity=2,
            policy_type=PolicyType.DIRECT,
        ),
    )


def test_direct_policy_returns_approved() -> None:
    policy = RegistrationPolicyFactory().create(PolicyType.DIRECT)
    assert policy.decide(make_context()).status is RegistrationStatus.APPROVED
    assert policy.requires_approval() is False


def test_audit_policy_returns_pending() -> None:
    policy = RegistrationPolicyFactory().create(PolicyType.APPROVAL)
    assert policy.decide(make_context()).status is RegistrationStatus.PENDING
    assert policy.requires_approval() is True


def test_pending_registration_can_be_approved_once() -> None:
    registration = make_registration(RegistrationStatus.PENDING)
    registration.approve()
    assert registration.status is RegistrationStatus.APPROVED
    with pytest.raises(InvalidTransitionError):
        registration.approve()


def test_approved_registration_can_be_cancelled() -> None:
    registration = make_registration(RegistrationStatus.APPROVED)
    registration.cancel()
    assert registration.status is RegistrationStatus.CANCELLED


def test_rejected_registration_cannot_be_cancelled() -> None:
    registration = make_registration(RegistrationStatus.REJECTED)
    with pytest.raises(InvalidTransitionError):
        registration.cancel()


def test_activity_start_window() -> None:
    activity = Activity(
        activity_id="A1",
        title="测试活动",
        category="讲座",
        start_at=datetime.now() + timedelta(hours=1),
        location="教学楼",
        capacity=2,
        policy_type=PolicyType.DIRECT,
    )
    assert activity.has_started() is False
    assert activity.has_started(datetime.now() + timedelta(hours=2)) is True
