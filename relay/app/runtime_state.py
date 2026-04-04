from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.config import BootstrapSettings, Settings, RuntimeConfig, resolve_settings
from app.diagnostics import build_environment_diagnostic_summary, build_runtime_diagnostic_report
from app.executors import ExecutorRegistry
from app.executors.base import ExecutorHealth
from app.models import ShareSubmissionRequest
from app.runtime_config import RuntimeConfigStore
from app.service import RelayService


class AppRuntime:
    def __init__(self, bootstrap: BootstrapSettings):
        self.bootstrap = bootstrap
        self.config_store = RuntimeConfigStore(bootstrap)
        self._runtime_config = self.config_store.load()
        self._settings = resolve_settings(self.bootstrap, self._runtime_config)
        self._service = RelayService(self._settings)
        self._service_generation = 0
        self._retired_services: list[RelayService] = []
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._cached_health: tuple[float, dict[str, Any]] | None = None
        self._cached_executor_healths: tuple[float, list[ExecutorHealth]] | None = None
        self._cached_diagnostic_report: tuple[float, dict[str, Any]] | None = None
        self._cached_environment_summary: tuple[float, str] | None = None

    @property
    def service(self) -> RelayService:
        return self._service

    @property
    def runtime_config(self) -> RuntimeConfig:
        return self._runtime_config

    @property
    def settings(self) -> Settings:
        return self._settings

    async def initialize(self) -> None:
        await self._service.initialize_runtime()
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def shutdown(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    def health_snapshot(self) -> dict:
        cached = self._cached_health
        now = time.monotonic()
        if cached is not None and now - cached[0] <= 2.0:
            return dict(cached[1])
        snapshot = self._service.health_snapshot()
        snapshot["webUiEnabled"] = self.bootstrap.web_ui_enabled
        snapshot["webUiLocalOnly"] = self.bootstrap.web_ui_local_only
        snapshot["runtimeConfigPath"] = str(self.bootstrap.runtime_config_path)
        snapshot["serviceGeneration"] = self._service_generation
        self._cached_health = (now, dict(snapshot))
        return snapshot

    def diagnostic_report(self) -> dict[str, Any]:
        cached = self._cached_diagnostic_report
        now = time.monotonic()
        if cached is not None and now - cached[0] <= 2.0:
            return dict(cached[1])
        health = self.health_snapshot()
        report = build_runtime_diagnostic_report(
            workspace_dir=str(self.bootstrap.workspace_dir),
            database_path=str(self.bootstrap.database_path),
            health=health,
            executor_healths=self.executor_healths(),
        )
        payload = report.as_dict()
        self._cached_diagnostic_report = (now, dict(payload))
        return payload

    def environment_diagnostic_summary(self) -> str:
        cached = self._cached_environment_summary
        now = time.monotonic()
        if cached is not None and now - cached[0] <= 2.0:
            return cached[1]
        health = self.health_snapshot()
        report = build_runtime_diagnostic_report(
            workspace_dir=str(self.bootstrap.workspace_dir),
            database_path=str(self.bootstrap.database_path),
            health=health,
            executor_healths=self.executor_healths(),
        )
        summary = build_environment_diagnostic_summary(
            service_name=self.bootstrap.service_name,
            service_version=self.bootstrap.service_version,
            health=health,
            report=report,
            runtime_config_path=str(self.bootstrap.runtime_config_path),
        )
        self._cached_environment_summary = (now, summary)
        return summary

    def config_metadata(self) -> dict[str, Any]:
        return {
            "runtimeConfigPath": str(self.bootstrap.runtime_config_path),
            "runtimeConfigVersion": self.config_store.current_payload()["configVersion"],
            "bootstrapSources": {
                "host": ".env / environment",
                "port": ".env / environment",
                "workspaceDir": ".env / environment",
                "authToken": ".env / environment",
                "serviceName": ".env / environment",
                "serviceVersion": ".env / environment",
                "webUiEnabled": ".env / environment",
                "webUiLocalOnly": ".env / environment",
            },
            "runtimeSources": {
                "defaultMode": "runtime config",
                "executorKind": "runtime config",
                "executorConfigs": "runtime config",
            },
            "applyScope": {
                "appliesToNewTasks": True,
                "runningTasksKeepConfigSnapshot": True,
                "restartRequiredFields": ["host", "port", "workspaceDir", "authToken", "webUiEnabled", "webUiLocalOnly"],
            },
        }

    def client_config(self):
        return self._service.client_config()

    def submit(self, payload):
        return self._service.submit(payload)

    def get_task_status(self, task_id: str):
        return self._service.get_task_status(task_id)

    def list_tasks(self, *, limit: int = 50, status: str | None = None, executor_kind: str | None = None, source: str | None = None):
        return self._service.list_tasks(limit=limit, status=status, executor_kind=executor_kind, source=source)

    def list_task_summaries(self, *, limit: int = 50, status: str | None = None, executor_kind: str | None = None, source: str | None = None):
        return self._service.list_task_summaries(limit=limit, status=status, executor_kind=executor_kind, source=source)

    def get_task_record(self, task_id: str):
        return self._service.get_task_record(task_id)

    def cancel_task(self, task_id: str):
        response = self._service.cancel_task(task_id)
        for service in self._retired_services:
            record = service.get_task_record(task_id)
            if record is None:
                continue
            try:
                service.executors.get(record.executor_kind or service.settings.executor_kind).cancel_task(task_id)
            except Exception:
                continue
        return response

    def executor_healths(self) -> list[ExecutorHealth]:
        cached = self._cached_executor_healths
        now = time.monotonic()
        if cached is not None and now - cached[0] <= 2.0:
            return list(cached[1])
        healths = [self._service.executors.get(descriptor.executorId).health() for descriptor in self._service.executors.descriptors()]
        self._cached_executor_healths = (now, list(healths))
        return healths

    def test_runtime_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        merged_dict = self.config_store.merge_preview(updates)
        runtime_config = self.config_store.runtime_from_dict(merged_dict)
        settings = resolve_settings(self.bootstrap, runtime_config)
        executors = ExecutorRegistry(settings, self._service.store)
        executor = executors.get(settings.executor_kind)
        health = executor.health()
        return {
            "runtimeConfig": runtime_config,
            "resolvedExecutor": settings.executor_kind,
            "executorHealth": {
                "executorId": health.executorId,
                "label": health.label,
                "available": health.available,
                "message": health.message,
                "details": health.details,
            },
        }

    async def smoke_test(self, smoke_kind: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="relay-smoke-") as tempdir:
            temp_root = Path(tempdir)
            workspace_dir = temp_root / "runtime"
            data_dir = workspace_dir / "data"
            tasks_dir = workspace_dir / "tasks"
            logs_dir = workspace_dir / "logs"
            for directory in (workspace_dir, data_dir, tasks_dir, logs_dir):
                directory.mkdir(parents=True, exist_ok=True)

            if smoke_kind == "mock":
                runtime_config = replace(
                    self.bootstrap.initial_runtime_config,
                    executor_kind="mock",
                    default_mode="paper_harvest_v1",
                )
            elif smoke_kind == "shell":
                command = _default_shell_smoke_template()
                runtime_config = replace(
                    self.bootstrap.initial_runtime_config,
                    executor_kind="shell_command",
                    default_mode="link_only_v1",
                    shell_command=replace(
                        self.bootstrap.initial_runtime_config.shell_command,
                        template=command,
                        timeout_seconds=30,
                    ),
                )
            elif smoke_kind == "openclaw":
                temp_runtime = AppRuntime(
                    replace(
                        self.bootstrap,
                        workspace_dir=workspace_dir,
                        data_dir=data_dir,
                        tasks_dir=tasks_dir,
                        logs_dir=logs_dir,
                        database_path=data_dir / "relay.sqlite3",
                        runtime_config_path=data_dir / "config.json",
                    )
                )
                await temp_runtime.initialize()
                health = temp_runtime.health_snapshot()
                report = temp_runtime.diagnostic_report()
                return {
                    "kind": "openclaw",
                    "status": "ok" if health.get("executorAvailable") else "warning",
                    "summary": "OpenClaw health checked.",
                    "health": health,
                    "diagnostics": report,
                }
            else:
                raise ValueError(f"Unsupported smoke kind: {smoke_kind}")

            smoke_bootstrap = replace(
                self.bootstrap,
                workspace_dir=workspace_dir,
                data_dir=data_dir,
                tasks_dir=tasks_dir,
                logs_dir=logs_dir,
                database_path=data_dir / "relay.sqlite3",
                runtime_config_path=data_dir / "config.json",
                initial_runtime_config=runtime_config,
            )
            smoke_runtime = AppRuntime(smoke_bootstrap)
            await smoke_runtime.initialize()
            payload = ShareSubmissionRequest(
                mode=runtime_config.default_mode,
                source="unknown",
                rawText="https://example.com/smoke",
                rawUrl="https://example.com/smoke",
                normalizedUrl="https://example.com/smoke",
                clientSubmissionId=f"smoke-{smoke_kind}",
                clientAppVersion="smoke",
            )
            response, _ = smoke_runtime.submit(payload)
            await smoke_runtime.service.run_task(response.taskId)
            task = smoke_runtime.get_task_status(response.taskId)
            return {
                "kind": smoke_kind,
                "status": task.status,
                "summary": task.problemTitle or task.resultSummary or task.stageLabel,
                "task": task.model_dump(),
            }

    async def update_runtime_config(self, updates: dict[str, Any]) -> RuntimeConfig:
        async with self._lock:
            updated = self.config_store.merge_and_save(updates)
            retired = self._service
            self._retired_services.append(retired)
            self._retired_services = self._retired_services[-3:]
            self._runtime_config = updated
            self._settings = resolve_settings(self.bootstrap, updated)
            self._service = RelayService(self._settings)
            self._service_generation += 1
            self._invalidate_caches()
            await self._service.initialize_runtime()
            return self._runtime_config

    async def _cleanup_loop(self) -> None:
        interval = max(60, self._settings.task_cleanup_interval_seconds)
        while True:
            await asyncio.sleep(interval)
            self._service.cleanup_old_tasks()

    def _invalidate_caches(self) -> None:
        self._cached_health = None
        self._cached_executor_healths = None
        self._cached_diagnostic_report = None
        self._cached_environment_summary = None


def _default_shell_smoke_template() -> str:
    if sys.platform.startswith("win"):
        return f'"{sys.executable}" -c "print(\'shell-smoke-ok\')"'
    return f"{sys.executable} -c \"print('shell-smoke-ok')\""
