from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models import TaskRecord


@dataclass(frozen=True)
class ExecutorDescriptor:
    executorId: str
    label: str
    supportsCancellation: bool
    supportsBrowserPrefetch: bool
    supportsStructuredResult: bool
    supportsRealtimeTimeline: bool
    supportedModeIds: tuple[str, ...]


@dataclass(frozen=True)
class ExecutorHealth:
    executorId: str
    label: str
    available: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class RelayTaskExecutor(ABC):
    executor_id = "base"
    display_name = "Base Executor"
    supports_cancellation = True
    supports_browser_prefetch = False
    supports_structured_result = True
    supports_realtime_timeline = True

    def __init__(self, settings, store):
        self.settings = settings
        self.store = store

    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executorId=self.executor_id,
            label=self.display_name,
            supportsCancellation=self.supports_cancellation,
            supportsBrowserPrefetch=self.supports_browser_prefetch,
            supportsStructuredResult=self.supports_structured_result,
            supportsRealtimeTimeline=self.supports_realtime_timeline,
            supportedModeIds=tuple(self.supported_mode_ids()),
        )

    @abstractmethod
    def health(self) -> ExecutorHealth:
        raise NotImplementedError

    def supports_mode(self, mode: str) -> bool:
        supported = self.supported_mode_ids()
        return not supported or mode in supported

    def supported_mode_ids(self) -> tuple[str, ...]:
        return ()

    def lane_key_for_task(self, task: TaskRecord) -> str:
        return f"executor:{self.executor_id}"

    def cancel_task(self, task_id: str) -> None:
        return

    @abstractmethod
    async def execute(self, task_id: str) -> None:
        raise NotImplementedError
