"""事件发布抽象与监听者契约。"""

from __future__ import annotations

from typing import Protocol

from project.domain.events import RegistrationStatusChangedEvent


class EventPublisher(Protocol):
    def publish(self, event: RegistrationStatusChangedEvent) -> None:
        ...


class NotificationListener(Protocol):
    def on_event(self, event: RegistrationStatusChangedEvent) -> None:
        ...
