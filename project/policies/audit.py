"""审核型报名策略：进入待审核。"""

from __future__ import annotations

from project.domain.enums import RegistrationStatus
from project.policies.base import PolicyDecision, RegistrationContext, RegistrationPolicy


class AuditPolicy(RegistrationPolicy):
    def decide(self, context: RegistrationContext) -> PolicyDecision:
        return PolicyDecision(status=RegistrationStatus.PENDING)

    def requires_approval(self) -> bool:
        return True
