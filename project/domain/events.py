"""领域事件契约（设计说明 5.2，编码阶段冻结命名）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from project.domain.enums import RegistrationStatus


@dataclass(frozen=True)
class RegistrationStatusChangedEvent:
    """报名状态变更事件：一次状态变更对应一条事件。"""

    registration_id: str
    student_id: str
    activity_id: str
    from_status: RegistrationStatus | None
    to_status: RegistrationStatus
    event_id: str = field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = field(default_factory=datetime.now)
