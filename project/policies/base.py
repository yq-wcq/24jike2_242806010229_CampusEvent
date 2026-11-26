"""报名策略抽象（设计说明 V2 3.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from project.domain.enums import RegistrationStatus
from project.domain.models import Activity, Student


@dataclass(frozen=True)
class RegistrationContext:
    """策略判断所需的上下文：只读，不含仓储。"""

    student: Student
    activity: Activity


@dataclass(frozen=True)
class PolicyDecision:
    """策略决策：给出初始状态，或给出拒绝原因。"""

    status: RegistrationStatus | None = None
    rejection_code: str | None = None
    rejection_message: str | None = None


class RegistrationPolicy(Protocol):
    """稳定的报名规则抽象：只做决策，不访问仓储、不写库。"""

    def decide(self, context: RegistrationContext) -> PolicyDecision:
        """报名提交时的初始状态或拒绝原因。"""
        ...

    def requires_approval(self) -> bool:
        """是否需要管理员审批。"""
        ...
