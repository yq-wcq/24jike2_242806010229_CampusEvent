"""策略工厂：把活动配置映射为策略实现，服务层不写类型分支。"""

from __future__ import annotations

from project.domain.enums import PolicyType
from project.policies.audit import AuditPolicy
from project.policies.base import RegistrationPolicy
from project.policies.direct import DirectPolicy


class RegistrationPolicyFactory:
    def __init__(self) -> None:
        self._policies: dict[PolicyType, RegistrationPolicy] = {
            PolicyType.DIRECT: DirectPolicy(),
            PolicyType.APPROVAL: AuditPolicy(),
        }

    def create(self, policy_type: PolicyType) -> RegistrationPolicy:
        try:
            return self._policies[PolicyType(policy_type)]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"不支持的报名方式：{policy_type}") from exc
