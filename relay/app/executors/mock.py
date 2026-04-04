from __future__ import annotations

import asyncio
import logging

from app.executors.base import ExecutorHealth
from app.executors.common import ManagedTaskExecutor, TaskCancelledError
from app.models import TaskRecord, utc_now_iso
from app.user_facing import result_summary_for_output

logger = logging.getLogger("relay.executor.mock")


class MockExecutor(ManagedTaskExecutor):
    executor_id = "mock"
    display_name = "Mock Executor"

    def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            executorId=self.executor_id,
            label=self.display_name,
            available=True,
            message="Mock executor is always available.",
        )

    def supported_mode_ids(self) -> tuple[str, ...]:
        return ("paper_harvest_v1", "paper_harvest_relaxed_v1", "link_only_v1")

    async def execute(self, task_id: str) -> None:
        task = self.store.get(task_id)
        if task is None:
            return

        task_dir = self._task_dir(task)
        self._write_task_snapshot(task_dir, task)
        logger.info("task_started task_id=%s mode=%s source=%s executor=%s", task.task_id, task.mode, task.source, self.executor_id)

        self._set_status(
            task_id,
            task_dir,
            status="preparing",
            stage_label="Preparing task",
            relay_message="Preparing the relay task.",
            started_at=utc_now_iso(),
            status_meta={"executorKind": self.executor_id, "phase": "preparing"},
        )

        try:
            await asyncio.sleep(0.2)
            if self._abort_if_cancelled(task_id, task_dir):
                return
            self._set_status(
                task_id,
                task_dir,
                status="running",
                stage_label="Fetching article",
                relay_message="Mock executor is simulating article fetch.",
                status_meta={"executorKind": self.executor_id, "phase": "fetching"},
            )

            await asyncio.sleep(0.2)
            if self._abort_if_cancelled(task_id, task_dir):
                return
            self._set_status(
                task_id,
                task_dir,
                status="finalizing",
                stage_label="Building result",
                relay_message="Mock executor is building a placeholder result.",
                status_meta={"executorKind": self.executor_id, "phase": "finalizing"},
            )

            await asyncio.sleep(0.2)
            if self._abort_if_cancelled(task_id, task_dir):
                return
            summary = self._build_mock_summary(task)
            self._write_text(task_dir / "result.txt", summary)
            self._set_status(
                task_id,
                task_dir,
                status="completed",
                stage_label="Completed",
                result_summary=summary,
                error_message="",
                error_code="",
                relay_message="Task completed successfully.",
                completed_at=utc_now_iso(),
                status_meta={"executorKind": self.executor_id, "phase": "completed"},
            )
            logger.info("task_completed task_id=%s executor=%s", task_id, self.executor_id)
        except TaskCancelledError:
            self._mark_cancelled(task_id, task_dir, "Relay task was cancelled.")

    def _build_mock_summary(self, task: TaskRecord) -> str:
        if task.mode == "link_only_v1":
            raw_summary = f"Mock executor confirmed the prepared link {task.normalized_url}"
        else:
            raw_summary = "\n".join(
                [
                    "Mock result ready.",
                    f"Mode: {task.mode}",
                    f"Source: {task.source}",
                    f"Prepared link: {task.normalized_url}",
                ]
            )
        return result_summary_for_output(
            mode=task.mode,
            executor_kind=self.executor_id,
            raw_summary=raw_summary,
            normalized_url=task.normalized_url,
            limit=self.settings.task_result_char_limit,
        )
