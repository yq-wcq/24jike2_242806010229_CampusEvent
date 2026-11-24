"""进程内同步事件总线（无消息队列）。"""

from __future__ import annotations

from project.domain.events import RegistrationStatusChangedEvent
from project.events.publisher import NotificationListener


class InProcessEventBus:
    def __init__(self) -> None:
        self._listeners: list[NotificationListener] = []

    def subscribe(self, listener: NotificationListener) -> None:
        """重复订阅同一监听者时忽略，避免重复通知。"""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def publish(self, event: RegistrationStatusChangedEvent) -> None:
        # 同步分发：一次 publish 对每个监听者只调用一次 on_event。
        for listener in list(self._listeners):
            listener.on_event(event)
