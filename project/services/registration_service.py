"""报名业务服务：编排校验、策略选择、状态变更与事件发布。

事务边界：``save`` / ``update`` 在仓储层各自独立提交，事件发布在提交之后；
V1 单机单实例假设下，find_active 与 save 之间的并发窗口接受。
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from project.domain.enums import RegistrationStatus
from project.domain.errors import (
    ActivityNotFoundError,
    ActivityStartedError,
    BusinessError,
    CapacityExceededError,
    DuplicateRegistrationError,
    ForbiddenError,
    InvalidTransitionError,
    RegistrationNotFoundError,
    StudentNotFoundError,
)
from project.domain.events import RegistrationStatusChangedEvent
from project.domain.models import Registration
from project.events.publisher import EventPublisher
from project.policies.base import RegistrationContext
from project.policies.factory import RegistrationPolicyFactory
from project.repositories.interfaces import (
    ActivityRepository,
    RegistrationRepository,
    StudentRepository,
)


class RegistrationService:
    def __init__(
        self,
        policy_factory: RegistrationPolicyFactory,
        activity_repository: ActivityRepository,
        registration_repository: RegistrationRepository,
        student_repository: StudentRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._policy_factory = policy_factory
        self._activity_repository = activity_repository
        self._registration_repository = registration_repository
        self._student_repository = student_repository
        self._event_publisher = event_publisher

    # ------------------------------------------------------------------
    def register(self, student_id: str, activity_id: str) -> Registration:
        # 1. 活动必须存在
        activity = self._activity_repository.find_by_id(activity_id)
        if activity is None:
            raise ActivityNotFoundError(f"活动不存在：{activity_id}")

        # 2. 活动未开始（B.2.5）
        if activity.has_started():
            raise ActivityStartedError("活动已开始，不允许新增报名")

        # 3. 查重：同一学生同一活动不得同时有 PENDING / APPROVED（B.2.4）
        existing = self._registration_repository.find_active(student_id, activity_id)
        if existing is not None:
            raise DuplicateRegistrationError(
                f"你在该活动已有有效报名（状态：{existing.status.value}）"
            )

        # 4. 学生必须存在（CR-01：策略需要读取年级）
        student = self._student_repository.find_by_id(student_id)
        if student is None:
            raise StudentNotFoundError(f"学生不存在：{student_id}")

        # 5. 策略给出决策：初始状态，或拒绝原因（CR-01 年级资格）
        policy = self._policy_factory.create(activity.policy_type)
        decision = policy.decide(
            RegistrationContext(student=student, activity=activity)
        )
        if decision.rejection_code:
            raise BusinessError(
                decision.rejection_message or "不满足报名条件",
                code=decision.rejection_code,
            )
        initial_status = decision.status
        if initial_status is None:
            raise BusinessError("报名策略未给出状态")

        # 6. 直接报名时再次校验名额（B.2.3：只有 APPROVED 占名额）
        if initial_status == RegistrationStatus.APPROVED:
            approved = self._registration_repository.count_approved(activity_id)
            if approved >= activity.capacity:
                raise CapacityExceededError("活动已报满")

        # 7. 写库（仓储层独立事务）
        now = datetime.now()
        registration = Registration(
            registration_id=uuid4().hex,
            activity_id=activity.activity_id,
            student_id=student_id,
            status=initial_status,
            created_at=now,
            updated_at=now,
        )
        registration = self._registration_repository.save(registration)

        # 8. 业务事务已提交，之后发布事件；通知异常不回滚（B.2.6）
        self._publish(registration, from_status=None)
        return registration

    # ------------------------------------------------------------------
    def cancel(self, student_id: str, registration_id: str) -> None:
        registration = self._registration_repository.find_by_id(registration_id)
        if registration is None:
            raise RegistrationNotFoundError(f"报名不存在：{registration_id}")

        if registration.student_id != student_id:
            raise ForbiddenError("只能取消自己的报名")

        from_status = registration.status
        registration.cancel()  # 状态机：PENDING/APPROVED → CANCELLED
        self._registration_repository.update(registration)

        # 事务已提交，再发布事件
        self._publish(registration, from_status=from_status)

    # ------------------------------------------------------------------
    def approve(self, registration_id: str) -> Registration:
        registration = self._registration_repository.find_by_id(registration_id)
        if registration is None:
            raise RegistrationNotFoundError(f"报名不存在：{registration_id}")

        # 同一事务内重新读取名额（单机接受短窗口）
        activity = self._activity_repository.find_by_id(registration.activity_id)
        if activity is None:
            raise ActivityNotFoundError("报名对应的活动不存在")

        from_status = registration.status
        try:
            registration.approve()
        except InvalidTransitionError as exc:
            raise exc  # PENDING 以外一律被状态机拒绝

        # 名额边界：审批时再次校验（C8）
        approved = self._registration_repository.count_approved(registration.activity_id)
        if approved >= activity.capacity:
            # 名额已满，回退状态变更
            registration.status = from_status
            registration.updated_at = datetime.now()
            self._registration_repository.update(registration)
            raise CapacityExceededError("审批时名额已满，无法批准")

        self._registration_repository.update(registration)
        self._publish(registration, from_status=from_status)
        return registration

    # ------------------------------------------------------------------
    def reject(self, registration_id: str) -> Registration:
        registration = self._registration_repository.find_by_id(registration_id)
        if registration is None:
            raise RegistrationNotFoundError(f"报名不存在：{registration_id}")

        from_status = registration.status
        registration.reject()  # 状态机：只允许 PENDING → REJECTED
        self._registration_repository.update(registration)

        self._publish(registration, from_status=from_status)
        return registration

    # ------------------------------------------------------------------
    def list_mine(self, student_id: str) -> list[Registration]:
        return self._registration_repository.list_by_student(student_id)

    def list_pending(self, activity_id: str) -> list[Registration]:
        return self._registration_repository.list_by_activity_status(
            activity_id, RegistrationStatus.PENDING
        )

    # ------------------------------------------------------------------ 内部
    def _publish(
        self, registration: Registration, *, from_status: RegistrationStatus | None
    ) -> None:
        event = RegistrationStatusChangedEvent(
            registration_id=registration.registration_id,
            student_id=registration.student_id,
            activity_id=registration.activity_id,
            from_status=from_status,
            to_status=registration.status,
        )
        # publish 内部已经吞掉异常（NotificationService.on_event 的 try/except）
        self._event_publisher.publish(event)
