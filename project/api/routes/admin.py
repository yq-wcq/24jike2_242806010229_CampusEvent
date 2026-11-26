"""管理员端：活动管理、审批与统计（F01/F05/F08）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from project.api.deps import (
    get_activity_service,
    get_email_service,
    get_registration_service,
)
from project.api.schemas import (
    ActivityCreate,
    ActivityOut,
    ActivityStatsOut,
    ActivityUpdate,
    EmailLogOut,
    RegistrationOut,
)
from project.services.activity_service import ActivityService
from project.services.email_service import EmailNotificationService
from project.services.registration_service import RegistrationService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED
)
def create_activity(
    payload: ActivityCreate,
    service: ActivityService = Depends(get_activity_service),
) -> ActivityOut:
    return service.create(**payload.model_dump())


@router.put("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: str,
    payload: ActivityUpdate,
    service: ActivityService = Depends(get_activity_service),
) -> ActivityOut:
    return service.update(activity_id, payload.model_dump(exclude_unset=True))


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: str,
    service: ActivityService = Depends(get_activity_service),
) -> Response:
    """无报名记录可删除；有任意历史报名则拒绝（T-S2）。"""
    service.delete(activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/activities/{activity_id}/stats", response_model=ActivityStatsOut)
def get_activity_stats(
    activity_id: str,
    service: ActivityService = Depends(get_activity_service),
) -> ActivityStatsOut:
    """完整统计仅管理员可见。"""
    return service.stats(activity_id)


@router.get(
    "/activities/{activity_id}/pending-registrations",
    response_model=list[RegistrationOut],
)
def list_pending_registrations(
    activity_id: str,
    service: RegistrationService = Depends(get_registration_service),
) -> list[RegistrationOut]:
    return service.list_pending(activity_id)


@router.post(
    "/registrations/{registration_id}/approve", response_model=RegistrationOut
)
def approve_registration(
    registration_id: str,
    service: RegistrationService = Depends(get_registration_service),
) -> RegistrationOut:
    """批准前重新校验名额，满员则失败（C8）。"""
    return service.approve(registration_id)


@router.post("/registrations/{registration_id}/reject", response_model=RegistrationOut)
def reject_registration(
    registration_id: str,
    service: RegistrationService = Depends(get_registration_service),
) -> RegistrationOut:
    return service.reject(registration_id)


@router.get("/email-logs", response_model=list[EmailLogOut])
def list_email_logs(
    limit: int = Query(default=50, ge=1, le=200),
    service: EmailNotificationService = Depends(get_email_service),
) -> list[EmailLogOut]:
    """模拟邮件发送记录；只读，用于验收与课堂演示（CR-02）。"""
    return service.list_recent(limit)
