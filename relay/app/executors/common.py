from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import time
from tempfile import SpooledTemporaryFile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.executors.base import RelayTaskExecutor
from app.models import TaskRecord, utc_now_iso


class TaskCancelledError(Exception):
    pass


class ManagedTaskExecutor(RelayTaskExecutor):
    def __init__(self, settings, store):
        super().__init__(settings, store)
        self._process_lock = threading.Lock()
        self._active_processes: dict[str, subprocess.Popen[str]] = {}

    def cancel_task(self, task_id: str) -> None:
        with self._process_lock:
            process = self._active_processes.get(task_id)
        if process is None:
            return
        self._terminate_process(process)

    def _task_dir(self, task: TaskRecord) -> Path:
        task_dir = Path(task.task_dir) if task.task_dir else (self.settings.tasks_dir / task.task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _write_task_snapshot(self, task_dir: Path, task: TaskRecord) -> None:
        payload = asdict(task)
        raw_text = payload.get("raw_text", "") or ""
        preview_limit = self.settings.task_request_preview_char_limit
        payload["raw_text_length"] = len(raw_text)
        payload["raw_text"] = self._trim_preview(raw_text, preview_limit)
        payload["raw_text_truncated"] = len(raw_text) > preview_limit
        (task_dir / "request.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_status_snapshot(task_dir, task)

    def _write_status_snapshot(self, task_dir: Path, task: TaskRecord) -> None:
        payload = task.to_status_response().model_dump()
        (task_dir / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def _set_status(self, task_id: str, task_dir: Path, **kwargs: Any) -> None:
        record = self.store.update_status(task_id, **kwargs)
        if record is not None:
            self._write_status_snapshot(task_dir, record)

    def _mark_failed(
        self,
        task_id: str,
        task_dir: Path,
        *,
        error_code: str,
        error_message: str,
        relay_message: str,
        status_meta: dict[str, Any] | None = None,
    ) -> None:
        if self._is_cancel_requested(task_id):
            self._mark_cancelled(
                task_id,
                task_dir,
                "Relay task was cancelled before the executor finished reporting this result.",
            )
            return
        merged_meta = {"executorKind": self.executor_id, "phase": "failed", "errorCode": error_code}
        if status_meta:
            merged_meta.update(status_meta)
        self._set_status(
            task_id,
            task_dir,
            status="failed",
            stage_label="Failed",
            error_message=self._trim_text(error_message, self.settings.task_error_char_limit),
            error_code=error_code,
            relay_message=relay_message,
            completed_at=utc_now_iso(),
            status_meta=merged_meta,
        )

    def _mark_cancelled(self, task_id: str, task_dir: Path, message: str) -> None:
        current = self.store.get(task_id)
        if current is not None and current.status == "completed":
            return
        self._set_status(
            task_id,
            task_dir,
            status="cancelled",
            stage_label="Cancelled",
            error_message="",
            error_code="",
            relay_message=message,
            completed_at=utc_now_iso(),
            status_meta={
                **(current.status_meta if current is not None else {}),
                "executorKind": self.executor_id,
                "phase": "cancelled",
                "cancelRequested": True,
            },
        )

    def _register_process(self, task_id: str | None, process: subprocess.Popen[str]) -> None:
        if not task_id:
            return
        with self._process_lock:
            self._active_processes[task_id] = process

    def _unregister_process(self, task_id: str | None, process: subprocess.Popen[str]) -> None:
        if not task_id:
            return
        with self._process_lock:
            if self._active_processes.get(task_id) is process:
                self._active_processes.pop(task_id, None)

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            if process.poll() is None:
                process.kill()

    def _is_cancel_requested(self, task_id: str) -> bool:
        task = self.store.get(task_id)
        if task is None:
            return False
        return task.status in {"cancelling", "cancelled"} or bool(task.status_meta.get("cancelRequested"))

    def _abort_if_cancelled(self, task_id: str, task_dir: Path) -> bool:
        if not self._is_cancel_requested(task_id):
            return False
        self._mark_cancelled(task_id, task_dir, "Relay task was cancelled.")
        return True

    async def _sleep_with_cancel_checks(self, task_id: str, task_dir: Path, wait_seconds: int) -> None:
        remaining = float(wait_seconds)
        while remaining > 0:
            if self._is_cancel_requested(task_id):
                raise TaskCancelledError("Cancellation requested.")
            step = min(0.5, remaining)
            await asyncio.sleep(step)
            remaining -= step

    async def _run_cli_process(
        self,
        command: list[str] | str,
        *,
        timeout_seconds: int,
        shell: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return await self._run_cancellable_process(command, task_id=None, timeout_seconds=timeout_seconds, shell=shell)

    async def _run_cancellable_process(
        self,
        command: list[str] | str,
        *,
        task_id: str | None,
        timeout_seconds: int,
        shell: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        with SpooledTemporaryFile(max_size=128 * 1024, mode="w+t", encoding="utf-8", errors="replace") as stdout_buffer:
            with SpooledTemporaryFile(max_size=128 * 1024, mode="w+t", encoding="utf-8", errors="replace") as stderr_buffer:
                process = subprocess.Popen(
                    command,
                    cwd=str(self.settings.workspace_dir),
                    stdout=stdout_buffer,
                    stderr=stderr_buffer,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=shell,
                )
                self._register_process(task_id, process)
                started = time.monotonic()
                try:
                    while True:
                        if process.poll() is not None:
                            stdout = self._read_spooled_text(stdout_buffer)
                            stderr = self._read_spooled_text(stderr_buffer)
                            return subprocess.CompletedProcess(command, process.returncode or 0, stdout, stderr)

                        if task_id and self._is_cancel_requested(task_id):
                            self._terminate_process(process)
                            process.wait(timeout=5)
                            stdout = self._read_spooled_text(stdout_buffer)
                            stderr = self._read_spooled_text(stderr_buffer)
                            raise TaskCancelledError(stderr.strip() or stdout.strip() or "Cancellation requested.")

                        if time.monotonic() - started > timeout_seconds:
                            self._terminate_process(process)
                            process.wait(timeout=5)
                            stdout = self._read_spooled_text(stdout_buffer)
                            stderr = self._read_spooled_text(stderr_buffer)
                            raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout, stderr=stderr)

                        await asyncio.sleep(0.1)
                finally:
                    self._unregister_process(task_id, process)

    def _trim_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        if limit <= 3:
            return text[:limit]
        return text[: limit - 3].rstrip() + "..."

    def _trim_preview(self, text: str, limit: int) -> str:
        return self._trim_text(text, limit)

    def _read_spooled_text(self, handle) -> str:
        handle.flush()
        handle.seek(0)
        return handle.read()
