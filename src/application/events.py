"""Thread-safe immutable application events with bounded replay."""

from __future__ import annotations

import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from src.application.event_log import SanitizedEventLog


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ApplicationEvent:
    event_id: int
    event_type: str
    timestamp: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(self.payload))


class EventSubscription:
    def __init__(self, hub: "EventHub", *, job_id: str | None = None, queue_size: int = 100):
        self._hub = hub
        self._job_id = job_id
        self._queue: queue.Queue[ApplicationEvent] = queue.Queue(maxsize=queue_size)
        self.closed = False
        self.needs_snapshot = False

    def accepts(self, event: ApplicationEvent) -> bool:
        return self._job_id is None or event.payload.get("job_id") == self._job_id

    def put(self, event: ApplicationEvent) -> None:
        if not self.closed and self.accepts(event):
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        break
                self.needs_snapshot = True

    def get(self, timeout: float | None = None) -> ApplicationEvent:
        return self._queue.get(timeout=timeout)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._hub._unsubscribe(self)

    def __enter__(self) -> "EventSubscription":
        return self

    def __exit__(self, *args) -> None:
        self.close()


class EventHub:
    def __init__(self, capacity: int = 1000, *, event_log: "SanitizedEventLog | None" = None):
        if capacity <= 0:
            raise ValueError("Event capacity must be positive")
        self._events: deque[ApplicationEvent] = deque(maxlen=capacity)
        self._subscribers: set[EventSubscription] = set()
        self._next_id = 1
        self._lock = threading.RLock()
        self._event_log = event_log

    def publish(self, event_type: str, payload: Mapping[str, Any]) -> ApplicationEvent:
        with self._lock:
            event = ApplicationEvent(
                event_id=self._next_id,
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                payload=payload,
            )
            self._next_id += 1
            self._events.append(event)
            subscribers = tuple(self._subscribers)
        if self._event_log is not None:
            self._event_log.append(event)
        for subscriber in subscribers:
            subscriber.put(event)
        return event

    def snapshot(
        self,
        *,
        after_id: int = 0,
        job_id: str | None = None,
    ) -> tuple[ApplicationEvent, ...]:
        with self._lock:
            return tuple(
                event
                for event in self._events
                if event.event_id > after_id
                and (job_id is None or event.payload.get("job_id") == job_id)
            )

    def subscribe(
        self,
        *,
        after_id: int | None = None,
        job_id: str | None = None,
        queue_size: int = 100,
    ) -> EventSubscription:
        subscription = EventSubscription(self, job_id=job_id, queue_size=queue_size)
        with self._lock:
            self._subscribers.add(subscription)
            replay = () if after_id is None else self.snapshot(after_id=after_id, job_id=job_id)
        for event in replay:
            subscription.put(event)
        return subscription

    def _unsubscribe(self, subscription: EventSubscription) -> None:
        with self._lock:
            self._subscribers.discard(subscription)
