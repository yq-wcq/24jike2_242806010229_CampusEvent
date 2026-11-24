"""学生端报名与取消（F03/F04）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from project.api.deps import get_registration_service
from project.api.schemas import RegistrationCreate, RegistrationOut
from project.services.registration_service import RegistrationService

router = APIRouter(prefix="/api", tags=["registrations"])


@router.post(
    "/activities/{activity_id}/registrations",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    activity_id: str,
    payload: RegistrationCreate,
    service: RegistrationService = Depends(get_registration_service),
) -> RegistrationOut:
    """报名：直接报名自动通过，审核型进入待审核。"""
    return service.register(payload.student_id, activity_id)


@router.get(
    "/students/{student_id}/registrations",
    response_model=list[RegistrationOut],
)
def list_my_registrations(
    student_id: str,
    service: RegistrationService = Depends(get_registration_service),
) -> list[RegistrationOut]:
    return service.list_mine(student_id)


@router.delete(
    "/students/{student_id}/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_registration(
    student_id: str,
    registration_id: str,
    service: RegistrationService = Depends(get_registration_service),
) -> Response:
    service.cancel(student_id, registration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
