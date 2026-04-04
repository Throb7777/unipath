from __future__ import annotations

import logging

from app.executors.base import ExecutorHealth
from app.executors.common import ManagedTaskExecutor, TaskCancelledError
from app.models import utc_now_iso
from app.user_facing import result_summary_for_output

logger = logging.getLogger("relay.executor.shell")


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class ShellCommandExecutor(ManagedTaskExecutor):
    executor_id = "shell_command"
    display_name = "Shell Command Executor"

    def health(self) -> ExecutorHealth:
        available = bool(self.settings.shell_command_template.strip())
        message = "Shell command template is configured." if available else "SHELL_COMMAND_TEMPLATE is empty."
        return ExecutorHealth(
            executorId=self.executor_id,
            label=self.display_name,
            available=available,
            message=message,
            details={"templateConfigured": available},
        )

    def supported_mode_ids(self) -> tuple[str, ...]:
        return ("link_only_v1",)

    async def execute(self, task_id: str) -> None:
        task = self.store.get(task_id)
        if task is None:
            return

        task_dir = self._task_dir(task)
        self._write_task_snapshot(task_dir, task)
        logger.info("task_started task_id=%s mode=%s source=%s executor=%s", task.task_id, task.mode, task.source, self.executor_id)

        if not self.settings.shell_command_template.strip():
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_command_not_configured",
                error_message="SHELL_COMMAND_TEMPLATE is empty.",
                relay_message="Shell command executor is not configured.",
            )
            return

        command = self._render_command(task)
        self._write_text(task_dir / "command.txt", command)
        self._set_status(
            task_id,
            task_dir,
            status="preparing",
            stage_label="Preparing task",
            relay_message="Preparing the shell-command task.",
            started_at=utc_now_iso(),
            status_meta={"executorKind": self.executor_id, "phase": "preparing"},
        )

        try:
            if self._abort_if_cancelled(task_id, task_dir):
                return
            self._set_status(
                task_id,
                task_dir,
                status="running",
                stage_label="Running executor",
                relay_message="Shell command executor is running.",
                status_meta={"executorKind": self.executor_id, "phase": "running"},
            )
            process = await self._run_cancellable_process(
                command,
                task_id=task_id,
                timeout_seconds=self.settings.shell_command_timeout_seconds,
                shell=True,
            )
        except TaskCancelledError:
            self._mark_cancelled(task_id, task_dir, "Relay task was cancelled while the shell command was running.")
            return
        except Exception as exc:
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_start_failed",
                error_message=f"Failed to start shell command executor: {exc}",
                relay_message="Relay could not start the shell command executor.",
            )
            return

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        if process.returncode != 0:
            self._write_text(task_dir / "stdout.txt", self._trim_text(stdout, self.settings.task_file_char_limit))
            self._write_text(task_dir / "stderr.txt", self._trim_text(stderr, self.settings.task_file_char_limit))
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_nonzero_exit",
                error_message=stderr or stdout or "Shell command exited with a non-zero code.",
                relay_message="Task failed during shell command execution.",
                status_meta={"executorKind": self.executor_id, "phase": "failed", "returnCode": process.returncode},
            )
            return

        self._set_status(
            task_id,
            task_dir,
            status="finalizing",
            stage_label="Finalizing result",
            relay_message="Finalizing the shell-command result.",
            status_meta={"executorKind": self.executor_id, "phase": "finalizing", "returnCode": process.returncode},
        )
        result_summary = result_summary_for_output(
            mode=task.mode,
            executor_kind=self.executor_id,
            raw_summary=stdout or "Shell command completed successfully.",
            normalized_url=task.normalized_url,
            limit=self.settings.task_result_char_limit,
        )
        self._write_text(task_dir / "result.txt", result_summary)
        if self.settings.task_keep_success_debug_files:
            self._write_text(task_dir / "stdout.txt", self._trim_text(stdout, self.settings.task_file_char_limit))
            if stderr.strip():
                self._write_text(task_dir / "stderr.txt", self._trim_text(stderr, self.settings.task_file_char_limit))
        else:
            (task_dir / "stdout.txt").unlink(missing_ok=True)
            (task_dir / "stderr.txt").unlink(missing_ok=True)
        self._set_status(
            task_id,
            task_dir,
            status="completed",
            stage_label="Completed",
            result_summary=result_summary,
            error_message="",
            error_code="",
            relay_message="Task completed successfully.",
            completed_at=utc_now_iso(),
            status_meta={"executorKind": self.executor_id, "phase": "completed", "returnCode": process.returncode},
        )
        logger.info("task_completed task_id=%s executor=%s", task_id, self.executor_id)

    def _render_command(self, task) -> str:
        template = self.settings.shell_command_template
        context = _SafeFormatDict(
            task_id=task.task_id,
            mode=task.mode,
            source=task.source,
            raw_text=task.raw_text,
            raw_url=task.raw_url or "",
            normalized_url=task.normalized_url,
            client_submission_id=task.client_submission_id,
            client_app_version=task.client_app_version,
        )
        return template.format_map(context)
