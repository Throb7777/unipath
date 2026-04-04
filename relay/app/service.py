from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

from app.config import Settings
from app.executors import ExecutorRegistry
from app.models import CancelTaskResponse, ClientConfigResponse, ShareSubmissionRequest, ShareSubmissionResponse, TaskStatusResponse
from app.modes import MODE_BY_ID, MODE_REGISTRY, list_client_modes
from app.store import TaskStore

logger = logging.getLogger("relay.service")
SUPPORTED_SOURCES = {"wechat_article", "xiaohongshu", "unknown"}


class RelayService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = TaskStore(settings.database_path)
        self.executors = ExecutorRegistry(settings, self.store)
        self._execution_semaphore: asyncio.Semaphore | None = None
        self._active_task_ids: set[str] = set()
        self._lane_locks: dict[str, asyncio.Lock] = {}
        self._startup_processed = False

    async def initialize_runtime(self) -> None:
        if self._execution_semaphore is None:
            self._execution_semaphore = asyncio.Semaphore(self.settings.max_concurrent_tasks)
        if self._startup_processed:
            return
        deleted_count = self.cleanup_old_tasks()
        if deleted_count:
            logger.info("task_cleanup removed=%s retention_days=%s", deleted_count, self.settings.task_retention_days)
        await self.recover_incomplete_tasks()
        self._startup_processed = True

    def health_snapshot(self) -> dict:
        selected_executor = self.executors.get_default()
        selected_health = selected_executor.health()
        runtime_writable = all(path.exists() for path in (self.settings.workspace_dir, self.settings.data_dir, self.settings.tasks_dir, self.settings.logs_dir))
        supported_default_modes = [mode.id for mode in MODE_REGISTRY if selected_executor.supports_mode(mode.id)]
        snapshot = {
            "service": self.settings.service_name,
            "version": self.settings.service_version,
            "status": "ok",
            "configuredExecutor": self.settings.executor_kind,
            "defaultMode": self.settings.default_mode,
            "supportedDefaultModes": supported_default_modes,
            "workspaceReady": self.settings.workspace_dir.exists(),
            "databaseReady": self.settings.database_path.exists(),
            "runtimeWritable": runtime_writable,
            "executorAvailable": selected_health.available,
            "executorMessage": selected_health.message,
            "maxConcurrentTasks": self.settings.max_concurrent_tasks,
            "startupRecoveryLimit": self.settings.startup_recovery_limit,
            "retentionDays": self.settings.task_retention_days,
            "availableExecutors": [
                {
                    "executorId": descriptor.executorId,
                    "label": descriptor.label,
                    "supportsCancellation": descriptor.supportsCancellation,
                    "supportsBrowserPrefetch": descriptor.supportsBrowserPrefetch,
                    "supportsStructuredResult": descriptor.supportsStructuredResult,
                    "supportsRealtimeTimeline": descriptor.supportsRealtimeTimeline,
                    "supportedModeIds": list(descriptor.supportedModeIds),
                }
                for descriptor in self.executors.descriptors()
            ],
        }
        if selected_health.details:
            snapshot["executorDetails"] = selected_health.details
        return snapshot

    def client_config(self) -> ClientConfigResponse:
        selected_executor = self.executors.get_default()
        default_mode = self.settings.default_mode if self.settings.default_mode in MODE_BY_ID else next(iter(MODE_BY_ID))
        if not selected_executor.supports_mode(default_mode):
            default_mode = next((mode.id for mode in MODE_REGISTRY if selected_executor.supports_mode(mode.id)), next(iter(MODE_BY_ID)))
        return ClientConfigResponse(
            serviceName=self.settings.service_name,
            serviceVersion=self.settings.service_version,
            defaultMode=default_mode,
            modes=list_client_modes(),
        )

    def submit(self, payload: ShareSubmissionRequest) -> tuple[ShareSubmissionResponse, bool]:
        self._validate_submission(payload)
        record, created = self.store.create_or_get(
            payload,
            executor_kind=self.settings.executor_kind,
            tasks_root=self.settings.tasks_dir,
        )
        event_name = "task_created" if created else "task_deduplicated"
        logger.info(
            "%s task_id=%s mode=%s source=%s executor=%s client_submission_id=%s",
            event_name,
            record.task_id,
            record.mode,
            record.source,
            record.executor_kind,
            record.client_submission_id,
        )
        return ShareSubmissionResponse(taskId=record.task_id, message="Accepted for relay processing."), created

    def get_task_status(self, task_id: str) -> TaskStatusResponse:
        record = self.store.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return record.to_status_response()

    def get_task_record(self, task_id: str):
        return self.store.get(task_id)

    def list_tasks(self, *, limit: int = 50, status: str | None = None, executor_kind: str | None = None, source: str | None = None):
        return self.store.list_tasks(limit=limit, status=status, executor_kind=executor_kind, source=source)

    def list_task_summaries(self, *, limit: int = 50, status: str | None = None, executor_kind: str | None = None, source: str | None = None):
        return self.store.list_task_summaries(limit=limit, status=status, executor_kind=executor_kind, source=source)

    def cancel_task(self, task_id: str) -> CancelTaskResponse:
        record = self.store.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if record.status in {"completed", "failed", "cancelled"}:
            return CancelTaskResponse(
                taskId=record.task_id,
                status=record.status,
                message=when_terminal_cancel_message(record.status),
                canCancel=False,
            )

        updated = self.store.request_cancel(
            task_id,
            relay_message="Cancellation requested. The relay is stopping this task.",
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Task not found")

        logger.info("task_cancel_requested task_id=%s status=%s", updated.task_id, updated.status)
        self.executors.get(updated.executor_kind or self.settings.executor_kind).cancel_task(task_id)
        return CancelTaskResponse(
            taskId=updated.task_id,
            status=updated.status,
            message="Cancellation requested.",
            canCancel=False,
        )

    async def run_task(self, task_id: str, *, recovered: bool = False) -> None:
        if self._execution_semaphore is None:
            self._execution_semaphore = asyncio.Semaphore(self.settings.max_concurrent_tasks)
        if task_id in self._active_task_ids:
            return

        semaphore = self._execution_semaphore
        if semaphore is None:
            return

        self._active_task_ids.add(task_id)
        try:
            if recovered:
                logger.info("task_recovered task_id=%s", task_id)
            async with semaphore:
                current = self.store.get(task_id)
                if current is None or current.status == "cancelled":
                    return
                if current.status == "cancelling":
                    self.store.update_status(
                        task_id,
                        status="cancelled",
                        stage_label="Cancelled",
                        relay_message="Task was cancelled before execution started.",
                        completed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        status_meta={**current.status_meta, "cancelledBeforeStart": True},
                    )
                    return

                executor = self.executors.get(current.executor_kind or self.settings.executor_kind)
                lane_key = executor.lane_key_for_task(current)
                lane_lock = self._lane_locks.setdefault(lane_key, asyncio.Lock())
                if lane_lock.locked() and current.status == "queued":
                    self.store.update_status(
                        task_id,
                        status="queued",
                        stage_label="Waiting for executor slot",
                        relay_message="Waiting for the executor lane to become available.",
                        status_meta={**current.status_meta, "laneKey": lane_key, "phase": "waiting_for_lane"},
                    )

                async with lane_lock:
                    current = self.store.get(task_id)
                    if current is None or current.status == "cancelled":
                        return
                    if current.status == "cancelling":
                        self.store.update_status(
                            task_id,
                            status="cancelled",
                            stage_label="Cancelled",
                            relay_message="Task was cancelled before executor work began.",
                            completed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            status_meta={**current.status_meta, "cancelledBeforeExecution": True, "laneKey": lane_key},
                        )
                        return
                    await executor.execute(task_id)
        finally:
            self._active_task_ids.discard(task_id)

    async def recover_incomplete_tasks(self) -> None:
        recoverable = self.store.list_recoverable(limit=self.settings.startup_recovery_limit)
        for index, record in enumerate(recoverable):
            if record.task_id in self._active_task_ids:
                continue
            if index > 0 and self.settings.startup_recovery_stagger_ms > 0:
                await asyncio.sleep(self.settings.startup_recovery_stagger_ms / 1000)
            asyncio.create_task(self.run_task(record.task_id, recovered=True))

    def cleanup_old_tasks(self) -> int:
        threshold = datetime.now(timezone.utc) - timedelta(days=self.settings.task_retention_days)
        threshold_iso = threshold.replace(microsecond=0).isoformat()
        stale_records = self.store.list_terminal_before(threshold_iso)
        if not stale_records:
            return 0

        removed_ids = [record.task_id for record in stale_records]
        deleted = self.store.delete_tasks(removed_ids)
        for record in stale_records:
            task_dir = Path(record.task_dir)
            if task_dir.exists():
                shutil.rmtree(task_dir, ignore_errors=True)
        return deleted

    def _validate_submission(self, payload: ShareSubmissionRequest) -> None:
        if payload.mode not in MODE_BY_ID:
            raise HTTPException(status_code=400, detail=f"Unsupported mode: {payload.mode}")
        if payload.source not in SUPPORTED_SOURCES:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {payload.source}")

        selected_executor = self.executors.get_default()
        if not selected_executor.supports_mode(payload.mode):
            raise HTTPException(
                status_code=400,
                detail=f"Configured executor '{self.settings.executor_kind}' does not support mode: {payload.mode}",
            )

        parsed = urlparse(payload.normalizedUrl)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="normalizedUrl must be a valid http(s) URL")


def when_terminal_cancel_message(status: str) -> str:
    if status == "completed":
        return "Task is already completed."
    if status == "cancelled":
        return "Task has already been cancelled."
    return "Task has already failed and cannot be cancelled."
