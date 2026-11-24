"""活动管理服务（F01/F02/F08）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from project.domain.enums import PolicyType
from project.domain.errors import (
    ActivityNotFoundError,
    CapacityExceededError,
    DeleteRejectedError,
)
from project.domain.models import Activity, ActivityStats
from project.repositories.interfaces import (
    ActivityRepository,
    RegistrationRepository,
)


class ActivityService:
    def __init__(
        self,
        activity_repository: ActivityRepository,
        registration_repository: RegistrationRepository,
    ) -> None:
        self._activity_repository = activity_repository
        self._registration_repository = registration_repository

    # ------------------------------------------------------------------ F01
    def create(
        self,
        *,
        title: str,
        category: str,
        start_at: datetime,
        location: str,
        capacity: int,
        policy_type: PolicyType,
    ) -> Activity:
        if not title or not title.strip():
            raise ValueError("活动名称不能为空")
        if capacity <= 0:
            raise ValueError("活动人数上限必须为正整数")
        activity = Activity(
            activity_id="",
            title=title.strip(),
            category=(category or "").strip(),
            start_at=start_at,
            location=location.strip(),
            capacity=capacity,
            policy_type=policy_type,
        )
        activity = self._activity_repository.save(activity)
        # 新创建的活动剩余名额 = 容量。
        activity.remaining_seats = activity.capacity
        return activity

    def update(self, activity_id: str, changes: dict[str, Any]) -> Activity:
        activity = self.get(activity_id)
        for field in ("title", "category", "start_at", "location", "capacity", "policy_type"):
            if field in changes and changes[field] is not None:
                setattr(activity, field, changes[field])

        # 本组补充假设：调小容量不得小于当前已通过人数。
        approved = self._registration_repository.count_approved(activity.activity_id)
        if activity.capacity < approved:
            raise CapacityExceededError(
                f"容量不能小于当前已通过人数（{approved}）"
            )

        updated = self._activity_repository.update(activity)
        updated.remaining_seats = max(updated.capacity - approved, 0)
        return updated

    def delete(self, activity_id: str) -> None:
        activity = self.get(activity_id)  # 不存在 → 抛 400
        if self._registration_repository.exists_any_by_activity(activity.activity_id):
            raise DeleteRejectedError(
                "活动存在报名记录，无法删除；如需清理请先手动处理相关报名"
            )
        self._activity_repository.delete(activity.activity_id)

    # ------------------------------------------------------------------ F02
    def list(self, keyword: str | None = None) -> list[Activity]:
        activities = self._activity_repository.list(keyword)
        # 学生端列表附带剩余名额。
        for activity in activities:
            approved = self._registration_repository.count_approved(activity.activity_id)
            activity.remaining_seats = max(activity.capacity - approved, 0)
        return activities

    def get(self, activity_id: str) -> Activity:
        activity = self._activity_repository.find_by_id(activity_id)
        if activity is None:
            raise ActivityNotFoundError(f"活动不存在：{activity_id}")
        approved = self._registration_repository.count_approved(activity.activity_id)
        activity.remaining_seats = max(activity.capacity - approved, 0)
        return activity

    # ------------------------------------------------------------------ F08
    def stats(self, activity_id: str) -> ActivityStats:
        activity = self.get(activity_id)
        approved = self._registration_repository.count_approved(activity.activity_id)
        pending = self._registration_repository.count_pending(activity.activity_id)
        return ActivityStats(
            activity_id=activity.activity_id,
            approved_count=approved,
            pending_count=pending,
            remaining_seats=max(activity.capacity - approved, 0),
        )
