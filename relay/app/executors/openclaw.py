from __future__ import annotations

import asyncio
import logging
import re
import shlex
import subprocess
from pathlib import Path

from app.executors.base import ExecutorHealth
from app.executors.common import ManagedTaskExecutor, TaskCancelledError
from app.executors.openclaw_browser import (
    analyze_wechat_article_text,
    classify_wechat_browser_text,
    decode_browser_text,
    extract_text_from_browser_snapshot,
)
from app.executors.openclaw_prompt import build_openclaw_command, build_openclaw_message
from app.modes import MODE_BY_ID
from app.models import TaskRecord, utc_now_iso
from app.openclaw_support import OpenClawCommandResolution, resolve_openclaw_command
from app.user_facing import result_summary_for_output

logger = logging.getLogger("relay.executor.openclaw")


class OpenClawExecutor(ManagedTaskExecutor):
    executor_id = "openclaw"
    display_name = "OpenClaw Executor"
    supports_browser_prefetch = True

    def health(self) -> ExecutorHealth:
        resolution = resolve_openclaw_command(self.settings.openclaw_command)
        target_value = self._target_value()
        details = {
            "targetMode": self.settings.openclaw_target_mode,
            "targetValue": target_value,
            "local": self.settings.openclaw_local,
            "browserProfile": self.settings.openclaw_browser_profile,
            "wechatBrowserPrefetch": self.settings.openclaw_wechat_use_browser,
            "resolvedPath": resolution.resolved_path or "",
            "displayCommand": resolution.display_command,
            "supportedModeIds": list(self.supported_mode_ids()),
        }
        return ExecutorHealth(
            executorId=self.executor_id,
            label=self.display_name,
            available=resolution.available,
            message="OpenClaw command is available." if resolution.available else "OpenClaw command could not be resolved.",
            details=details,
        )

    def supported_mode_ids(self) -> tuple[str, ...]:
        return tuple(MODE_BY_ID.keys())

    def lane_key_for_task(self, task: TaskRecord) -> str:
        return f"openclaw:{self.settings.openclaw_target_mode}:{self._target_value()}"

    async def execute(self, task_id: str) -> None:
        task = self.store.get(task_id)
        if task is None:
            return

        task_dir = self._task_dir(task)
        self._write_task_snapshot(task_dir, task)
        logger.info("task_started task_id=%s mode=%s source=%s executor=%s", task.task_id, task.mode, task.source, self.executor_id)

        resolution = resolve_openclaw_command(self.settings.openclaw_command)
        if not resolution.available:
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_command_not_found",
                error_message=f"OpenClaw command could not be resolved: {self.settings.openclaw_command}",
                relay_message="Relay could not find the configured OpenClaw command.",
            )
            return

        self._set_status(
            task_id,
            task_dir,
            status="preparing",
            stage_label="Preparing task",
            relay_message="Preparing the OpenClaw task.",
            started_at=utc_now_iso(),
            status_meta=self._status_meta("preparing", resolution),
        )

        try:
            if self._abort_if_cancelled(task_id, task_dir):
                return

            article_prefetch = await self._maybe_prefetch_article(task, task_dir, resolution)
            article_body = article_prefetch["body"]
            if article_body is None and self._prefetch_was_required(task):
                return

            if self._abort_if_cancelled(task_id, task_dir):
                return

            prompt = build_openclaw_message(self.settings, task, article_body=article_body)
            command = build_openclaw_command(self.settings, task, prompt, resolution)
            self._write_text(task_dir / "prompt.txt", prompt)
            self._write_text(task_dir / "command.txt", self._format_command(command))

            self._set_status(
                task_id,
                task_dir,
                status="running",
                stage_label="Running executor",
                relay_message="OpenClaw executor is running.",
                status_meta=self._status_meta("running", resolution),
            )

            process = await self._run_with_retries(task, task_dir, command, resolution)
        except TaskCancelledError:
            self._mark_cancelled(task_id, task_dir, "Relay task was cancelled while OpenClaw was running.")
            return
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.output or "").strip()
            stderr = (exc.stderr or "").strip()
            self._persist_process_output(task_dir, stdout, stderr)
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_timeout",
                error_message=stderr or stdout or "OpenClaw timed out.",
                relay_message="OpenClaw timed out before producing a result.",
                status_meta=self._status_meta("failed", resolution, return_code=-1),
            )
            return
        except Exception as exc:
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_start_failed",
                error_message=f"Failed to run OpenClaw executor: {exc}",
                relay_message="Relay could not start the OpenClaw executor.",
            )
            return

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        if process.returncode != 0:
            self._persist_process_output(task_dir, stdout, stderr, keep_always=True)
            error_code, relay_message = self._classify_process_failure(stdout, stderr)
            self._mark_failed(
                task_id,
                task_dir,
                error_code=error_code,
                error_message=stderr or stdout or "OpenClaw exited with a non-zero code.",
                relay_message=relay_message,
                status_meta=self._status_meta(
                    "failed",
                    resolution,
                    return_code=process.returncode,
                    article_prefetch=article_prefetch,
                ),
            )
            logger.warning("task_failed task_id=%s executor=%s error_code=%s", task_id, self.executor_id, error_code)
            return

        self._set_status(
            task_id,
            task_dir,
            status="finalizing",
            stage_label="Finalizing result",
            relay_message="Finalizing the OpenClaw result.",
            status_meta=self._status_meta(
                "finalizing",
                resolution,
                return_code=process.returncode,
                article_prefetch=article_prefetch,
            ),
        )

        raw_result = stdout.strip() or stderr.strip() or "OpenClaw completed successfully."
        if self._reports_failure(raw_result):
            reason = self._extract_reason(raw_result) or raw_result
            self._mark_failed(
                task_id,
                task_dir,
                error_code="executor_reported_failure",
                error_message=reason,
                relay_message="OpenClaw reported a failed task result.",
                status_meta=self._status_meta(
                    "failed",
                    resolution,
                    return_code=process.returncode,
                    article_prefetch=article_prefetch,
                ),
            )
            logger.warning("task_failed task_id=%s executor=%s error_code=%s", task_id, self.executor_id, "executor_reported_failure")
            return

        summary = self._normalize_result_summary(task, stdout, stderr)
        self._write_text(task_dir / "result.txt", summary)
        self._persist_process_output(
            task_dir,
            stdout,
            stderr,
            keep_always=self.settings.task_keep_success_debug_files,
        )
        self._cleanup_success_artifacts(task_dir)

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
            status_meta=self._status_meta(
                "completed",
                resolution,
                return_code=process.returncode,
                article_prefetch=article_prefetch,
            ),
        )
        logger.info(
            "task_completed task_id=%s executor=%s target_mode=%s",
            task_id,
            self.executor_id,
            self.settings.openclaw_target_mode,
        )

    async def _maybe_prefetch_article(
        self,
        task: TaskRecord,
        task_dir: Path,
        resolution: OpenClawCommandResolution,
    ) -> dict[str, object]:
        if not self._prefetch_was_required(task):
            return {"body": None, "noisy_markers": []}

        self._set_status(
            task.task_id,
            task_dir,
            status="running",
            stage_label="Opening browser",
            relay_message="Opening the managed browser to fetch the article body.",
            status_meta=self._status_meta("browser_prefetch", resolution),
        )

        await self._run_browser_command(task.task_id, resolution, "start")
        open_result = await self._run_browser_command(task.task_id, resolution, "open", task.normalized_url)
        target_id = self._extract_browser_target_id(open_result.stdout)
        await self._run_browser_command(task.task_id, resolution, "wait", "--time", "750", "--timeout-ms", "10000")
        raw_body, decoded = await self._fetch_browser_article_body(
            task.task_id,
            task_dir,
            resolution,
            url=task.normalized_url,
            target_id=target_id,
        )
        if raw_body:
            self._write_text(task_dir / "browser_body_raw.txt", raw_body)
        if decoded:
            self._write_text(task_dir / "browser_body.txt", decoded)

        classified = classify_wechat_browser_text(decoded)
        if classified is not None:
            error_code, error_message, relay_message = classified
            self._mark_failed(task.task_id, task_dir, error_code=error_code, error_message=error_message, relay_message=relay_message)
            logger.warning("task_failed task_id=%s executor=%s error_code=%s", task.task_id, self.executor_id, error_code)
            return {"body": None, "noisy_markers": []}

        analysis = analyze_wechat_article_text(decoded)
        cleaned = analysis.cleaned_text
        if cleaned:
            self._write_text(task_dir / "browser_body_cleaned.txt", cleaned)
        if len(cleaned.strip()) < 120:
            self._mark_failed(
                task.task_id,
                task_dir,
                error_code="wechat_body_too_short",
                error_message="The fetched WeChat article body was too short to trust as a full article.",
                relay_message="The fetched WeChat article body was too short to use.",
            )
            logger.warning("task_failed task_id=%s executor=%s error_code=%s", task.task_id, self.executor_id, "wechat_body_too_short")
            return {"body": None, "noisy_markers": list(analysis.noisy_markers)}
        return {"body": cleaned, "noisy_markers": list(analysis.noisy_markers)}

    async def _fetch_browser_article_body(
        self,
        task_id: str,
        task_dir: Path,
        resolution: OpenClawCommandResolution,
        *,
        url: str,
        target_id: str | None,
    ) -> tuple[str, str]:
        response_args = [
            "responsebody",
            url,
            "--max-chars",
            str(self.settings.task_file_char_limit),
            "--timeout-ms",
            str(min(60000, self.settings.openclaw_timeout_seconds * 1000)),
        ]
        if target_id:
            response_args.extend(["--target-id", target_id])
        try:
            response = await self._run_browser_command(task_id, resolution, *response_args)
            raw_body = response.stdout.strip()
            return raw_body, decode_browser_text(raw_body)
        except RuntimeError as exc:
            error_text = str(exc)
            self._write_text(task_dir / "browser_body_stderr.txt", error_text)
            if "gateway timeout" not in error_text.lower():
                raise
            snapshot_text = await self._capture_browser_snapshot(task_id, resolution, target_id)
            if not snapshot_text.strip():
                raise
            self._write_text(task_dir / "browser_snapshot.txt", snapshot_text)
            extracted_text = extract_text_from_browser_snapshot(snapshot_text)
            return snapshot_text, extracted_text or snapshot_text

    async def _capture_browser_snapshot(
        self,
        task_id: str,
        resolution: OpenClawCommandResolution,
        target_id: str | None,
    ) -> str:
        snapshot_args = ["snapshot", "--limit", "220"]
        if target_id:
            snapshot_args.extend(["--target-id", target_id])
        result = await self._run_browser_command(task_id, resolution, *snapshot_args)
        return result.stdout.strip()

    async def _run_browser_command(
        self,
        task_id: str,
        resolution: OpenClawCommandResolution,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            *resolution.invocation_prefix,
            "browser",
            "--browser-profile",
            self.settings.openclaw_browser_profile,
            *args,
        ]
        result = await self._run_cancellable_process(
            command,
            task_id=task_id,
            timeout_seconds=min(90, self.settings.openclaw_timeout_seconds),
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OpenClaw browser command failed.")
        return result

    async def _run_with_retries(
        self,
        task: TaskRecord,
        task_dir: Path,
        command: list[str],
        resolution: OpenClawCommandResolution,
    ) -> subprocess.CompletedProcess[str]:
        lock_attempt = 0
        network_attempt = 0
        defer_cycle = 0

        while True:
            process = await self._run_cancellable_process(
                command,
                task_id=task.task_id,
                timeout_seconds=self.settings.openclaw_timeout_seconds,
            )
            combined = self._combined_output(process.stdout, process.stderr)
            if process.returncode == 0:
                return process

            if self._is_session_lock_error(combined):
                if lock_attempt < self.settings.openclaw_session_lock_retry_attempts:
                    lock_attempt += 1
                    wait_seconds = self.settings.openclaw_session_lock_retry_base_seconds * lock_attempt
                    self._set_status(
                        task.task_id,
                        task_dir,
                        status="running",
                        stage_label="Retrying executor lock",
                        relay_message=f"Executor lane is busy. Retrying in {wait_seconds}s.",
                        status_meta=self._status_meta("retrying_executor_lock", resolution, return_code=process.returncode),
                    )
                    await self._sleep_with_cancel_checks(task.task_id, task_dir, wait_seconds)
                    continue
                if defer_cycle < self.settings.openclaw_session_lock_defer_cycles:
                    defer_cycle += 1
                    lock_attempt = 0
                    wait_seconds = self.settings.openclaw_session_lock_defer_seconds * defer_cycle
                    self._set_status(
                        task.task_id,
                        task_dir,
                        status="queued",
                        stage_label="Waiting for executor slot",
                        relay_message=f"Waiting {wait_seconds}s for the OpenClaw lane to become available.",
                        status_meta=self._status_meta("waiting_for_lane", resolution, return_code=process.returncode),
                    )
                    await self._sleep_with_cancel_checks(task.task_id, task_dir, wait_seconds)
                    self._set_status(
                        task.task_id,
                        task_dir,
                        status="running",
                        stage_label="Running executor",
                        relay_message="Retrying the OpenClaw executor.",
                        status_meta=self._status_meta("running", resolution),
                    )
                    continue
                return process

            if self._is_network_error(combined) and network_attempt < self.settings.openclaw_network_retry_attempts:
                network_attempt += 1
                wait_seconds = self.settings.openclaw_network_retry_base_seconds * network_attempt
                self._set_status(
                    task.task_id,
                    task_dir,
                    status="running",
                    stage_label="Retrying network request",
                    relay_message=f"OpenClaw hit a network issue. Retrying in {wait_seconds}s.",
                    status_meta=self._status_meta("retrying_network", resolution, return_code=process.returncode),
                )
                await self._sleep_with_cancel_checks(task.task_id, task_dir, wait_seconds)
                continue

            return process

    def _prefetch_was_required(self, task: TaskRecord) -> bool:
        mode = MODE_BY_ID.get(task.mode)
        if mode is None:
            return False
        return (
            task.source == "wechat_article"
            and self.settings.openclaw_wechat_use_browser
            and mode.requiresArticleBodyFetch
            and mode.supportsBrowserPrefetch
        )

    def _combined_output(self, stdout: str, stderr: str) -> str:
        parts = [part.strip() for part in (stdout, stderr) if part and part.strip()]
        return "\n".join(parts)

    def _persist_process_output(self, task_dir: Path, stdout: str, stderr: str, *, keep_always: bool = False) -> None:
        if keep_always or stderr.strip():
            self._write_text(task_dir / "stderr.txt", self._trim_text(stderr, self.settings.task_file_char_limit))
        elif not self.settings.task_keep_success_debug_files:
            (task_dir / "stderr.txt").unlink(missing_ok=True)

        if keep_always:
            self._write_text(task_dir / "stdout.txt", self._trim_text(stdout, self.settings.task_file_char_limit))
        elif not self.settings.task_keep_success_debug_files:
            (task_dir / "stdout.txt").unlink(missing_ok=True)

    def _cleanup_success_artifacts(self, task_dir: Path) -> None:
        if self.settings.task_keep_success_debug_files:
            return
        for name in (
            "browser_snapshot.txt",
            "browser_body_raw.txt",
            "browser_body.txt",
            "browser_body_stderr.txt",
        ):
            (task_dir / name).unlink(missing_ok=True)

    def _classify_process_failure(self, stdout: str, stderr: str) -> tuple[str, str]:
        combined = self._combined_output(stdout, stderr).lower()
        if self._is_session_lock_error(combined):
            return ("executor_session_locked", "OpenClaw session is busy. Try again after the current run finishes.")
        if self._is_network_error(combined):
            return ("executor_network_error", "OpenClaw hit a provider or network error while processing this task.")
        if "no api key found" in combined or "auth" in combined:
            return ("executor_auth_error", "OpenClaw authentication is not configured correctly on this machine.")
        if "timed out" in combined or "timeout" in combined:
            return ("executor_timeout", "OpenClaw timed out before finishing this task.")
        return ("executor_nonzero_exit", "Task failed during OpenClaw execution.")

    def _normalize_result_summary(self, task: TaskRecord, stdout: str, stderr: str) -> str:
        candidate = stdout.strip() or stderr.strip() or "OpenClaw completed successfully."
        return result_summary_for_output(
            mode=task.mode,
            executor_kind=self.executor_id,
            raw_summary=candidate,
            normalized_url=task.normalized_url,
            limit=self.settings.task_result_char_limit,
        )

    def _reports_failure(self, summary: str) -> bool:
        return "STATUS: failed" in summary

    def _extract_reason(self, summary: str) -> str:
        for line in summary.splitlines():
            if line.startswith("REASON:"):
                return line.partition(":")[2].strip()
        return ""

    def _status_meta(
        self,
        phase: str,
        resolution: OpenClawCommandResolution,
        *,
        return_code: int | None = None,
        article_prefetch: dict[str, object] | None = None,
    ) -> dict[str, object]:
        meta: dict[str, object] = {
            "executorKind": self.executor_id,
            "phase": phase,
            "openclawLocal": self.settings.openclaw_local,
            "openclawTargetMode": self.settings.openclaw_target_mode,
            "resolvedPath": resolution.resolved_path or "",
        }
        if self.settings.openclaw_target_mode == "agent":
            meta["openclawAgentId"] = self.settings.openclaw_agent_id
        if self.settings.openclaw_target_mode == "session" and self.settings.openclaw_session_id:
            meta["openclawSessionId"] = self.settings.openclaw_session_id
        if self.settings.openclaw_target_mode == "to" and self.settings.openclaw_to:
            meta["openclawTo"] = self.settings.openclaw_to
        if return_code is not None:
            meta["returnCode"] = return_code
        if article_prefetch:
            noisy_markers = [marker for marker in article_prefetch.get("noisy_markers", []) if isinstance(marker, str)]
            if noisy_markers:
                meta["bodyPossiblyNoisy"] = True
                meta["bodyNoiseMarkers"] = noisy_markers
        return meta

    def _format_command(self, command: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in command)

    def _extract_browser_target_id(self, output: str) -> str | None:
        match = re.search(r"^id:\s*([A-Za-z0-9]+)$", output or "", re.MULTILINE)
        return match.group(1) if match else None

    def _target_value(self) -> str:
        if self.settings.openclaw_target_mode == "session":
            return self.settings.openclaw_session_id or "(session)"
        if self.settings.openclaw_target_mode == "to":
            return self.settings.openclaw_to or "(recipient)"
        return self.settings.openclaw_agent_id or "(agent)"

    def _is_session_lock_error(self, text: str) -> bool:
        lowered = text.lower()
        return "session file locked" in lowered or ".jsonl.lock" in lowered

    def _is_network_error(self, text: str) -> bool:
        lowered = text.lower()
        return "network connection error" in lowered or "fetch failed" in lowered
