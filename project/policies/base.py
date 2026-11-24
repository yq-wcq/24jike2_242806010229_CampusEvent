"""报名策略抽象（设计说明 5.1）。"""

from __future__ import annotations

from typing import Protocol

from project.domain.enums import RegistrationStatus


class RegistrationPolicy(Protocol):
    """稳定的报名规则抽象：只决定初始状态，不做名额校验。"""

    def initial_status(self) -> RegistrationStatus:
        """报名提交成功后写入的初始状态。"""
        ...

    def requires_approval(self) -> bool:
        """是否需要管理员审批。"""
        ...
