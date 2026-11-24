"""直接报名策略：自动通过。"""

from __future__ import annotations

from project.domain.enums import RegistrationStatus
from project.policies.base import RegistrationPolicy


class DirectPolicy(RegistrationPolicy):
    def initial_status(self) -> RegistrationStatus:
        return RegistrationStatus.APPROVED

    def requires_approval(self) -> bool:
        return False
