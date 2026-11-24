"""领域枚举。"""

from __future__ import annotations

from enum import Enum


class PolicyType(str, Enum):
    """活动的报名方式。"""

    DIRECT = "DIRECT"
    APPROVAL = "APPROVAL"


class RegistrationStatus(str, Enum):
    """报名状态，只允许这四种。"""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    @property
    def is_active(self) -> bool:
        """有效报名：待审核或已通过（B.2.4）。"""
        return self in (RegistrationStatus.PENDING, RegistrationStatus.APPROVED)
