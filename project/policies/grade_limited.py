"""年级限定直接报名策略（CR-01）：仅大二、大三可报名。"""

from __future__ import annotations

from project.domain.enums import RegistrationStatus
from project.policies.base import PolicyDecision, RegistrationContext, RegistrationPolicy

ALLOWED_GRADES = frozenset({2, 3})


class GradeLimitedDirectPolicy(RegistrationPolicy):
    def decide(self, context: RegistrationContext) -> PolicyDecision:
        if context.student.grade in ALLOWED_GRADES:
            return PolicyDecision(status=RegistrationStatus.APPROVED)
        return PolicyDecision(
            rejection_code="GRADE_NOT_ELIGIBLE",
            rejection_message="该活动仅面向大二、大三学生",
        )

    def requires_approval(self) -> bool:
        return False
