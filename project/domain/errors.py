"""业务异常。异常信息直接返回给前端，不暴露内部细节。"""

from __future__ import annotations


class BusinessError(Exception):
    """业务规则失败，统一映射为 HTTP 400。"""

    code = "BUSINESS_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ActivityNotFoundError(BusinessError):
    code = "ACTIVITY_NOT_FOUND"


class RegistrationNotFoundError(BusinessError):
    code = "REGISTRATION_NOT_FOUND"


class ActivityStartedError(BusinessError):
    code = "ACTIVITY_STARTED"


class DuplicateRegistrationError(BusinessError):
    code = "DUPLICATE_REGISTRATION"


class CapacityExceededError(BusinessError):
    code = "CAPACITY_EXCEEDED"


class InvalidTransitionError(BusinessError):
    code = "INVALID_STATUS_TRANSITION"


class DeleteRejectedError(BusinessError):
    code = "DELETE_REJECTED"


class ForbiddenError(BusinessError):
    code = "FORBIDDEN"
