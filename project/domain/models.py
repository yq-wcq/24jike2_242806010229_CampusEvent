"""领域模型。V1 约定时间为本地时间（Asia/Shanghai），以 ISO 字符串持久化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from project.domain.enums import PolicyType, RegistrationStatus
from project.domain.errors import InvalidTransitionError


@dataclass
class Student:
    student_id: str
    name: str


@dataclass
class Activity:
    activity_id: str
    title: str
    category: str
    start_at: datetime
    location: str
    capacity: int
    policy_type: PolicyType

    def has_started(self, now: datetime | None = None) -> bool:
        """活动开始后不允许新增报名（B.2.5）。"""
        return (now or datetime.now()) >= self.start_at


@dataclass
class Registration:
    registration_id: str
    activity_id: str
    student_id: str
    status: RegistrationStatus
    created_at: datetime
    updated_at: datetime

    def approve(self) -> None:
        self._transition({RegistrationStatus.PENDING}, RegistrationStatus.APPROVED)

    def reject(self) -> None:
        self._transition({RegistrationStatus.PENDING}, RegistrationStatus.REJECTED)

    def cancel(self) -> None:
        self._transition(
            {RegistrationStatus.PENDING, RegistrationStatus.APPROVED},
            RegistrationStatus.CANCELLED,
        )

    def _transition(
        self,
        allowed: set[RegistrationStatus],
        target: RegistrationStatus,
    ) -> None:
        if self.status not in allowed:
            raise InvalidTransitionError(
                f"报名状态不允许从 {self.status.value} 变更为 {target.value}"
            )
        self.status = target
        self.updated_at = datetime.now()


@dataclass
class Message:
    message_id: str
    student_id: str
    activity_id: str
    content: str
    created_at: datetime
    is_read: bool = False


@dataclass(frozen=True)
class ActivityStats:
    """F08 统计口径：只有已通过占名额。"""

    activity_id: str
    approved_count: int
    pending_count: int
    remaining_seats: int
