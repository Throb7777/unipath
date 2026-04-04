from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.models import ShareSubmissionRequest
from app.service import RelayService


def make_settings(root: Path, **overrides) -> Settings:
    workspace_dir = root / "runtime"
    data_dir = workspace_dir / "data"
    tasks_dir = workspace_dir / "tasks"
    logs_dir = workspace_dir / "logs"
    for directory in (workspace_dir, data_dir, tasks_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    values = {
        "host": "127.0.0.1",
        "port": 18080,
        "auth_token": "",
        "service_name": "Test Relay",
        "service_version": "0.1.0",
        "default_mode": "paper_harvest_v1",
        "executor_kind": "mock",
        "shell_command_template": "",
        "shell_command_timeout_seconds": 30,
        "openclaw_command": "openclaw",
        "openclaw_target_mode": "agent",
        "openclaw_local": True,
        "openclaw_agent_id": "main",
        "openclaw_session_id": "",
        "openclaw_to": "",
        "openclaw_channel": "",
        "openclaw_thinking": "",
        "openclaw_json_output": False,
        "openclaw_browser_profile": "openclaw",
        "openclaw_wechat_use_browser": True,
        "openclaw_timeout_seconds": 30,
        "openclaw_session_lock_retry_attempts": 2,
        "openclaw_session_lock_retry_base_seconds": 1,
        "openclaw_session_lock_defer_cycles": 1,
        "openclaw_session_lock_defer_seconds": 1,
        "openclaw_network_retry_attempts": 2,
        "openclaw_network_retry_base_seconds": 1,
        "max_concurrent_tasks": 2,
        "startup_recovery_limit": 25,
        "startup_recovery_stagger_ms": 0,
        "task_retention_days": 30,
        "task_result_char_limit": 800,
        "task_error_char_limit": 1200,
        "task_file_char_limit": 12000,
        "task_cleanup_interval_seconds": 43200,
        "task_request_preview_char_limit": 2000,
        "task_keep_success_debug_files": False,
        "workspace_dir": workspace_dir,
        "data_dir": data_dir,
        "tasks_dir": tasks_dir,
        "logs_dir": logs_dir,
        "database_path": data_dir / "relay.sqlite3",
        "web_ui_enabled": True,
        "web_ui_local_only": True,
        "runtime_config_path": data_dir / "config.json",
    }
    values.update(overrides)
    return Settings(**values)


def make_payload(client_submission_id: str):
    return {
        "mode": "paper_harvest_v1",
        "source": "wechat_article",
        "rawText": "https://example.com/article",
        "rawUrl": "https://example.com/article",
        "normalizedUrl": "https://example.com/article",
        "clientSubmissionId": client_submission_id,
        "clientAppVersion": "1.0",
    }


class RelayCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_executor_completes_task(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            settings = make_settings(Path(tempdir), executor_kind="mock")
            service = RelayService(settings)
            await service.initialize_runtime()

            response, created = service.submit(ShareSubmissionRequest(**make_payload("mock-1")))
            self.assertTrue(created)
            await service.run_task(response.taskId)

            status = service.get_task_status(response.taskId)
            self.assertEqual(status.status, "completed")
            self.assertIn("Mock result", status.resultSummary)
            self.assertIn("Highlights:", status.resultSummary)
            self.assertIn("Review the result summary", status.diagnosticSummary)

    async def test_shell_command_executor_completes_task(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            template = f'"{sys.executable}" -c "print(\'shell executor ok\')"'
            settings = make_settings(Path(tempdir), executor_kind="shell_command", shell_command_template=template)
            service = RelayService(settings)
            await service.initialize_runtime()

            payload = make_payload("shell-1")
            payload["mode"] = "link_only_v1"
            response, created = service.submit(ShareSubmissionRequest(**payload))
            self.assertTrue(created)
            await service.run_task(response.taskId)

            status = service.get_task_status(response.taskId)
            self.assertEqual(status.status, "completed")
            self.assertIn("shell executor ok", status.resultSummary)
            self.assertEqual(status.problemTitle, "Task completed")

    async def test_failed_task_exposes_problem_title_and_suggested_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            settings = make_settings(Path(tempdir), executor_kind="shell_command", shell_command_template="")
            service = RelayService(settings)
            await service.initialize_runtime()

            payload = make_payload("shell-missing-template")
            payload["mode"] = "link_only_v1"
            response, created = service.submit(ShareSubmissionRequest(**payload))
            self.assertTrue(created)
            await service.run_task(response.taskId)

            status = service.get_task_status(response.taskId)
            self.assertEqual(status.status, "failed")
            self.assertEqual(status.problemTitle, "Command template is missing")
            self.assertTrue(status.suggestedActions)
            self.assertIn("Open Settings", status.diagnosticSummary)

    async def test_cancel_before_execution_marks_task_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            settings = make_settings(Path(tempdir), executor_kind="mock")
            service = RelayService(settings)
            await service.initialize_runtime()

            response, _ = service.submit(ShareSubmissionRequest(**make_payload("cancel-1")))
            cancel_response = service.cancel_task(response.taskId)
            self.assertIn(cancel_response.status, {"cancelling", "cancelled"})
            await service.run_task(response.taskId)

            status = service.get_task_status(response.taskId)
            self.assertEqual(status.status, "cancelled")

    async def test_health_lists_available_executors(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            settings = make_settings(Path(tempdir), executor_kind="mock")
            service = RelayService(settings)
            await service.initialize_runtime()

            snapshot = service.health_snapshot()
            executors = {item["executorId"]: item for item in snapshot["availableExecutors"]}
            self.assertIn("mock", executors)
            self.assertIn("openclaw", executors)
            self.assertIn("shell_command", executors)
            self.assertTrue(executors["mock"]["supportsStructuredResult"])
            self.assertIn("paper_harvest_v1", executors["openclaw"]["supportedModeIds"])
            self.assertEqual(executors["shell_command"]["supportedModeIds"], ["link_only_v1"])


if __name__ == "__main__":
    unittest.main()
