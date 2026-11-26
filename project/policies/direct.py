"""直接报名策略：自动通过。"""

from __future__ import annotations

from project.domain.enums import RegistrationStatus
from project.policies.base import PolicyDecision, RegistrationContext, RegistrationPolicy


class DirectPolicy(RegistrationPolicy):
    def decide(self, context: RegistrationContext) -> PolicyDecision:
        return PolicyDecision(status=RegistrationStatus.APPROVED)

    def requires_approval(self) -> bool:
        return False
