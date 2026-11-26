"""模拟邮件通知订阅者（CR-02）。

设计约束：
- 只处理 APPROVED / REJECTED，站内消息与 PENDING 行为不变；
- 在业务事务提交后由事件总线调用，任何异常只记录日志，不回滚报名；
- 依赖 ``email_logs.event_id`` 唯一约束做持久化去重。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from project.domain.enums import EmailStatus, RegistrationStatus
from project.domain.events import RegistrationStatusChangedEvent
from project.domain.models import EmailLog
from project.events.publisher import NotificationListener
from project.repositories.interfaces import EmailLogRepository, StudentRepository

logger = logging.getLogger(__name__)

_SUBJECTS: dict[RegistrationStatus, str] = {
    RegistrationStatus.APPROVED: "报名结果：已通过",
    RegistrationStatus.REJECTED: "报名结果：未通过",
}

_CONTENTS: dict[RegistrationStatus, str] = {
    RegistrationStatus.APPROVED: "您报名的活动已通过审核，请按时参加。",
    RegistrationStatus.REJECTED: "很抱歉，您报名的活动未通过审核。",
}


class EmailSender(Protocol):
    def send(self, *, recipient: str, subject: str, content: str) -> None:
        """发送失败时抛出异常，由订阅者捕获。"""
        ...


class MockEmailSender:
    """教学用模拟发送器：不连接真实邮件服务，仅代表发送成功。"""

    def send(self, *, recipient: str, subject: str, content: str) -> None:
        return None


class EmailNotificationService(NotificationListener):
    def __init__(
        self,
        student_repository: StudentRepository,
        email_log_repository: EmailLogRepository,
        sender: EmailSender,
    ) -> None:
        self._student_repository = student_repository
        self._email_log_repository = email_log_repository
        self._sender = sender

    def on_event(self, event: RegistrationStatusChangedEvent) -> None:
        if event.to_status not in _SUBJECTS:
            return
        if self._email_log_repository.exists_by_event(event.event_id):
            return

        student = self._student_repository.find_by_id(event.student_id)
        recipient = (
            student.email
            if student is not None and student.email
            else f"{event.student_id}@campus.example"
        )
        subject = _SUBJECTS[event.to_status]
        content = f"{_CONTENTS[event.to_status]}（活动ID：{event.activity_id}）"

        status = EmailStatus.SENT
        error: str | None = None
        try:
            self._sender.send(recipient=recipient, subject=subject, content=content)
        except Exception as exc:  # 通知失败不影响已提交的业务（B.2.6）
            status = EmailStatus.FAILED
            error = str(exc)
            logger.exception(
                "模拟邮件发送失败，不影响已提交的业务：event_id=%s registration_id=%s",
                event.event_id,
                event.registration_id,
            )

        try:
            self._email_log_repository.save(
                EmailLog(
                    email_id=uuid4().hex,
                    event_id=event.event_id,
                    registration_id=event.registration_id,
                    student_id=event.student_id,
                    recipient=recipient,
                    subject=subject,
                    content=content,
                    status=status,
                    created_at=datetime.now(),
                    error=error,
                )
            )
        except Exception:
            # 唯一约束兜底：并发或重复事件已写入时跳过。
            logger.exception(
                "邮件记录写入失败（可能为重复事件）：event_id=%s", event.event_id
            )

    def list_recent(self, limit: int = 50) -> list[EmailLog]:
        return self._email_log_repository.list_recent(limit)
