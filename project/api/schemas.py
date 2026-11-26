"""API 请求/响应模型（对外契约）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from project.domain.enums import EmailStatus, PolicyType, RegistrationStatus


class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, description="活动名称")
    category: str = ""
    start_at: datetime
    location: str = Field(min_length=1)
    capacity: int = Field(gt=0, description="人数上限，必须为正整数")
    policy_type: PolicyType


class ActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    category: str | None = None
    start_at: datetime | None = None
    location: str | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, gt=0)
    policy_type: PolicyType | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_id: str
    title: str
    category: str
    start_at: datetime
    location: str
    capacity: int
    policy_type: PolicyType
    remaining_seats: int | None = Field(
        default=None, description="学生端只展示剩余名额；完整统计见管理员统计接口"
    )


class RegistrationCreate(BaseModel):
    student_id: str = Field(min_length=1)


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: str
    activity_id: str
    student_id: str
    status: RegistrationStatus
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    student_id: str
    activity_id: str
    content: str
    created_at: datetime
    is_read: bool


class ActivityStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_id: str
    approved_count: int
    pending_count: int
    remaining_seats: int


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_id: str
    event_id: str
    registration_id: str
    student_id: str
    recipient: str
    subject: str
    content: str
    status: EmailStatus
    error: str | None = None
    created_at: datetime


class ErrorOut(BaseModel):
    code: str
    message: str
