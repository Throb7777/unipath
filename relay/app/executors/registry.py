from __future__ import annotations

from app.executors.base import ExecutorDescriptor
from app.executors.mock import MockExecutor
from app.executors.openclaw import OpenClawExecutor
from app.executors.shell_command import ShellCommandExecutor


EXECUTOR_TYPES = {
    "mock": MockExecutor,
    "openclaw": OpenClawExecutor,
    "shell_command": ShellCommandExecutor,
}


class ExecutorRegistry:
    def __init__(self, settings, store):
        self.settings = settings
        self.store = store
        self._executors = {executor_id: executor_cls(settings, store) for executor_id, executor_cls in EXECUTOR_TYPES.items()}

    def get(self, executor_id: str):
        try:
            return self._executors[executor_id]
        except KeyError as exc:
            raise KeyError(f"Unknown executor: {executor_id}") from exc

    def get_default(self):
        return self.get(self.settings.executor_kind)

    def descriptors(self) -> list[ExecutorDescriptor]:
        return [executor.descriptor() for executor in self._executors.values()]

    def ids(self) -> list[str]:
        return list(self._executors.keys())
