"""站内消息查询（F07）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from project.api.deps import get_notification_service
from project.api.schemas import MessageOut
from project.services.notification_service import NotificationService

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/students/{student_id}/messages", response_model=list[MessageOut])
def list_messages(
    student_id: str,
    service: NotificationService = Depends(get_notification_service),
) -> list[MessageOut]:
    return service.list_by_student(student_id)
