"""学生端活动浏览（F02）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from project.api.deps import get_activity_service
from project.api.schemas import ActivityOut
from project.services.activity_service import ActivityService

router = APIRouter(prefix="/api", tags=["activities"])


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    keyword: str | None = None,
    service: ActivityService = Depends(get_activity_service),
) -> list[ActivityOut]:
    """活动列表，可按名称筛选。"""
    return service.list(keyword)


@router.get("/activities/{activity_id}", response_model=ActivityOut)
def get_activity(
    activity_id: str,
    service: ActivityService = Depends(get_activity_service),
) -> ActivityOut:
    """活动详情。"""
    return service.get(activity_id)
