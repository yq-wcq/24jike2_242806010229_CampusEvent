"""站内通知服务：订阅报名状态变更事件（F07）。

事务边界：本服务在业务事务提交后由事件总线调用；任何异常只记录日志，
绝不向上抛出，也绝不回滚已提交的报名/审批结果（B.2.6）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from project.domain.enums import RegistrationStatus
from project.domain.events import RegistrationStatusChangedEvent
from project.domain.models import Message
from project.events.publisher import NotificationListener
from project.repositories.interfaces import MessageRepository

logger = logging.getLogger(__name__)

_MESSAGE_TEMPLATES: dict[RegistrationStatus, str] = {
    RegistrationStatus.APPROVED: "您报名的活动审核结果：已通过。",
    RegistrationStatus.PENDING: "报名已提交，正在等待管理员审核。",
    RegistrationStatus.REJECTED: "您报名的活动审核结果：已拒绝。",
}


class NotificationService(NotificationListener):
    def __init__(self, message_repository: MessageRepository) -> None:
        self._message_repository = message_repository
        # V1 单进程内存去重：进程重启后集合清空，但 V1 无事件重放来源。
        self._processed_event_ids: set[str] = set()

    def on_event(self, event: RegistrationStatusChangedEvent) -> None:
        if event.event_id in self._processed_event_ids:
            return
        try:
            self._write_message(event)
        except Exception:
            logger.exception(
                "站内通知写入失败，不影响已提交的业务：event_id=%s registration_id=%s",
                event.event_id,
                event.registration_id,
            )
            return
        self._processed_event_ids.add(event.event_id)

    def _write_message(self, event: RegistrationStatusChangedEvent) -> None:
        template = _MESSAGE_TEMPLATES.get(event.to_status)
        if template is None:
            return
        message = Message(
            message_id=uuid4().hex,
            student_id=event.student_id,
            activity_id=event.activity_id,
            content=f"{template}（活动ID：{event.activity_id}）",
            created_at=datetime.now(),
        )
        self._message_repository.save(message)

    def list_by_student(self, student_id: str) -> list[Message]:
        return self._message_repository.list_by_student(student_id)
