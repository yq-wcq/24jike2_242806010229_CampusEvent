"""依赖装配：单例仓储、事件总线与服务。"""

from __future__ import annotations

from functools import lru_cache

from project.config import settings
from project.events.bus import InProcessEventBus
from project.policies.factory import RegistrationPolicyFactory
from project.repositories.interfaces import (
    ActivityRepository,
    EmailLogRepository,
    MessageRepository,
    RegistrationRepository,
    StudentRepository,
)
from project.repositories.sqlite import (
    SqliteActivityRepository,
    SqliteEmailLogRepository,
    SqliteMessageRepository,
    SqliteRegistrationRepository,
    SqliteStudentRepository,
)
from project.services.activity_service import ActivityService
from project.services.email_service import (
    EmailNotificationService,
    EmailSender,
    MockEmailSender,
)
from project.services.notification_service import NotificationService
from project.services.registration_service import RegistrationService


@lru_cache
def get_event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@lru_cache
def get_activity_repository() -> ActivityRepository:
    return SqliteActivityRepository(settings.database_path)


@lru_cache
def get_registration_repository() -> RegistrationRepository:
    return SqliteRegistrationRepository(settings.database_path)


@lru_cache
def get_message_repository() -> MessageRepository:
    return SqliteMessageRepository(settings.database_path)


@lru_cache
def get_student_repository() -> StudentRepository:
    return SqliteStudentRepository(settings.database_path)


@lru_cache
def get_email_log_repository() -> EmailLogRepository:
    return SqliteEmailLogRepository(settings.database_path)


@lru_cache
def get_email_sender() -> EmailSender:
    return MockEmailSender()


@lru_cache
def get_email_service() -> EmailNotificationService:
    return EmailNotificationService(
        student_repository=get_student_repository(),
        email_log_repository=get_email_log_repository(),
        sender=get_email_sender(),
    )


@lru_cache
def get_notification_service() -> NotificationService:
    return NotificationService(get_message_repository())


def get_activity_service() -> ActivityService:
    return ActivityService(get_activity_repository(), get_registration_repository())


def get_registration_service() -> RegistrationService:
    return RegistrationService(
        policy_factory=RegistrationPolicyFactory(),
        activity_repository=get_activity_repository(),
        registration_repository=get_registration_repository(),
        student_repository=get_student_repository(),
        event_publisher=get_event_bus(),
    )
