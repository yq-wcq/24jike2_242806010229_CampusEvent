"""仓储接口（依赖倒置，服务层只依赖这些抽象）。"""

from __future__ import annotations

from typing import Protocol

from project.domain.enums import RegistrationStatus
from project.domain.models import Activity, EmailLog, Message, Registration, Student


class StudentRepository(Protocol):
    def find_by_id(self, student_id: str) -> Student | None:
        ...


class ActivityRepository(Protocol):
    def find_by_id(self, activity_id: str) -> Activity | None:
        ...

    def list(self, keyword: str | None = None) -> list[Activity]:
        ...

    def save(self, activity: Activity) -> Activity:
        ...

    def update(self, activity: Activity) -> Activity:
        ...

    def delete(self, activity_id: str) -> None:
        ...


class RegistrationRepository(Protocol):
    def find_by_id(self, registration_id: str) -> Registration | None:
        ...

    def find_active(self, student_id: str, activity_id: str) -> Registration | None:
        """查询该学生该活动的 PENDING/APPROVED 记录（B.2.4）。"""
        ...

    def exists_any_by_activity(self, activity_id: str) -> bool:
        """是否存在任意状态的报名记录（删除校验，T-S2）。"""
        ...

    def count_approved(self, activity_id: str) -> int:
        ...

    def count_pending(self, activity_id: str) -> int:
        ...

    def save(self, registration: Registration) -> Registration:
        ...

    def update(self, registration: Registration) -> Registration:
        ...

    def list_by_student(self, student_id: str) -> list[Registration]:
        ...

    def list_by_activity_status(
        self, activity_id: str, status: RegistrationStatus
    ) -> list[Registration]:
        ...


class MessageRepository(Protocol):
    def save(self, message: Message) -> Message:
        ...

    def list_by_student(self, student_id: str) -> list[Message]:
        ...


class EmailLogRepository(Protocol):
    def exists_by_event(self, event_id: str) -> bool:
        ...

    def save(self, log: EmailLog) -> EmailLog:
        ...

    def list_recent(self, limit: int = 50) -> list[EmailLog]:
        ...
