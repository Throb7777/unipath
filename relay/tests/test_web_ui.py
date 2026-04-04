from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from dataclasses import replace

from app.config import BootstrapSettings, OpenClawRuntimeConfig, RuntimeConfig, ShellCommandRuntimeConfig
from app.http_app import create_app
from app.models import ShareSubmissionRequest


def make_bootstrap(root: Path) -> BootstrapSettings:
    workspace_dir = root / "runtime"
    data_dir = workspace_dir / "data"
    tasks_dir = workspace_dir / "tasks"
    logs_dir = workspace_dir / "logs"
    for directory in (workspace_dir, data_dir, tasks_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return BootstrapSettings(
        host="127.0.0.1",
        port=18080,
        auth_token="",
        service_name="Relay UI Test",
        service_version="0.1.0",
        workspace_dir=workspace_dir,
        data_dir=data_dir,
        tasks_dir=tasks_dir,
        logs_dir=logs_dir,
        database_path=data_dir / "relay.sqlite3",
        runtime_config_path=data_dir / "config.json",
        web_ui_enabled=True,
        web_ui_local_only=True,
        initial_runtime_config=RuntimeConfig(
            default_mode="paper_harvest_v1",
            executor_kind="mock",
            shell_command=ShellCommandRuntimeConfig(template="", timeout_seconds=30),
            openclaw=OpenClawRuntimeConfig(
                command="openclaw",
                target_mode="agent",
                local=True,
                agent_id="main",
                session_id="",
                to="",
                channel="",
                thinking="",
                json_output=False,
                browser_profile="openclaw",
                wechat_use_browser=True,
                timeout_seconds=30,
                session_lock_retry_attempts=2,
                session_lock_retry_base_seconds=1,
                session_lock_defer_cycles=1,
                session_lock_defer_seconds=1,
                network_retry_attempts=2,
                network_retry_base_seconds=1,
            ),
        ),
    )


class WebUiTests(unittest.TestCase):
    def test_web_ui_pages_and_settings_save(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))

            static_css = client.get("/static/app.css")
            self.assertEqual(static_css.status_code, 200)
            self.assertIn("body {", static_css.text)

            index = client.get("/ui")
            self.assertEqual(index.status_code, 200)
            self.assertIn("Local relay companion", index.text)
            self.assertIn("Ready for new tasks", index.text)
            self.assertIn("Quick actions", index.text)
            self.assertIn("Copy UI URL", index.text)
            self.assertIn("Relay ready", index.text)
            self.assertIn("Processing Method", index.text)

            settings_page = client.get("/ui/settings")
            self.assertEqual(settings_page.status_code, 200)
            self.assertIn("⚙️ Settings", settings_page.text)
            self.assertIn("Basic settings", settings_page.text)
            self.assertIn("Task defaults", settings_page.text)
            self.assertIn("Recommended when you want full article extraction.", settings_page.text)

            save = client.post(
                "/ui/settings",
                data={
                    "default_mode": "link_only_v1",
                    "executor_kind": "shell_command",
                    "shell_command_template": "echo {normalized_url}",
                    "shell_command_timeout_seconds": "55",
                    "openclaw_command": "openclaw",
                    "openclaw_target_mode": "agent",
                    "openclaw_local": "on",
                    "openclaw_agent_id": "main",
                    "openclaw_session_id": "",
                    "openclaw_to": "",
                    "openclaw_channel": "",
                    "openclaw_thinking": "",
                    "openclaw_browser_profile": "openclaw",
                    "openclaw_timeout_seconds": "30",
                    "openclaw_session_lock_retry_attempts": "2",
                    "openclaw_session_lock_retry_base_seconds": "1",
                    "openclaw_session_lock_defer_cycles": "1",
                    "openclaw_session_lock_defer_seconds": "1",
                    "openclaw_network_retry_attempts": "2",
                    "openclaw_network_retry_base_seconds": "1",
                },
                follow_redirects=True,
            )
            self.assertEqual(save.status_code, 200)
            self.assertIn("Settings saved", save.text)

            app_runtime = client.app.state.runtime
            self.assertEqual(app_runtime.runtime_config.executor_kind, "shell_command")
            self.assertEqual(app_runtime.runtime_config.default_mode, "link_only_v1")

    def test_web_ui_settings_test_executor_action(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))

            result = client.post(
                "/ui/settings",
                data={
                    "_action": "test",
                    "default_mode": "link_only_v1",
                    "executor_kind": "shell_command",
                    "shell_command_template": "echo {normalized_url}",
                    "shell_command_timeout_seconds": "40",
                    "openclaw_command": "openclaw",
                    "openclaw_target_mode": "agent",
                    "openclaw_local": "on",
                    "openclaw_agent_id": "main",
                    "openclaw_session_id": "",
                    "openclaw_to": "",
                    "openclaw_channel": "",
                    "openclaw_thinking": "",
                    "openclaw_browser_profile": "openclaw",
                    "openclaw_timeout_seconds": "30",
                    "openclaw_session_lock_retry_attempts": "2",
                    "openclaw_session_lock_retry_base_seconds": "1",
                    "openclaw_session_lock_defer_cycles": "1",
                    "openclaw_session_lock_defer_seconds": "1",
                    "openclaw_network_retry_attempts": "2",
                    "openclaw_network_retry_base_seconds": "1",
                },
            )
            self.assertEqual(result.status_code, 200)
            self.assertIn("Processing method test:", result.text)
            self.assertIn("Shell Command Executor", result.text)
            self.assertIn("available", result.text)

            save_test = client.post(
                "/ui/settings",
                data={
                    "_action": "save_test",
                    "default_mode": "link_only_v1",
                    "executor_kind": "shell_command",
                    "shell_command_template": "echo {normalized_url}",
                    "shell_command_timeout_seconds": "40",
                    "openclaw_command": "openclaw",
                    "openclaw_target_mode": "agent",
                    "openclaw_local": "on",
                    "openclaw_agent_id": "main",
                    "openclaw_session_id": "",
                    "openclaw_to": "",
                    "openclaw_channel": "",
                    "openclaw_thinking": "",
                    "openclaw_browser_profile": "openclaw",
                    "openclaw_timeout_seconds": "30",
                    "openclaw_session_lock_retry_attempts": "2",
                    "openclaw_session_lock_retry_base_seconds": "1",
                    "openclaw_session_lock_defer_cycles": "1",
                    "openclaw_session_lock_defer_seconds": "1",
                    "openclaw_network_retry_attempts": "2",
                    "openclaw_network_retry_base_seconds": "1",
                },
            )
            self.assertEqual(save_test.status_code, 200)
            self.assertIn("Settings saved", save_test.text)
            self.assertIn("Processing method test:", save_test.text)

    def test_web_ui_tasks_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))
            runtime = client.app.state.runtime
            payload = ShareSubmissionRequest(
                mode="paper_harvest_v1",
                source="wechat_article",
                rawText="https://example.com/article",
                rawUrl="https://example.com/article",
                normalizedUrl="https://example.com/article",
                clientSubmissionId="web-ui-task-1",
                clientAppVersion="1.0",
            )
            response, created = runtime.submit(payload)
            self.assertTrue(created)
            task_dir = bootstrap.tasks_dir / response.taskId
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "prompt.txt").write_text("hello", encoding="utf-8")
            (task_dir / "result.txt").write_text("done", encoding="utf-8")

            tasks_page = client.get("/ui/tasks")
            self.assertEqual(tasks_page.status_code, 200)
            self.assertIn(response.taskId, tasks_page.text)

            detail = client.get(f"/ui/tasks/{response.taskId}")
            self.assertEqual(detail.status_code, 200)
            self.assertIn(response.taskId, detail.text)
            self.assertIn("Task Files", detail.text)
            self.assertIn("prompt.txt", detail.text)
            self.assertIn("Diagnostic Summary", detail.text)
            self.assertIn("Copy Diagnostic Summary", detail.text)

            diagnostics = client.get("/ui/diagnostics")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertIn("Processing method status", diagnostics.text)
            self.assertIn("Configuration behavior", diagnostics.text)
            self.assertIn("Selected processing method", diagnostics.text)
            self.assertIn("Follow-up Suggestions", diagnostics.text)
            self.assertIn("Processing method looks ready", diagnostics.text)

    def test_web_ui_task_list_uses_problem_and_next_step_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))
            runtime = client.app.state.runtime
            payload = ShareSubmissionRequest(
                mode="paper_harvest_v1",
                source="wechat_article",
                rawText="https://example.com/bad",
                rawUrl="https://example.com/bad",
                normalizedUrl="https://example.com/bad",
                clientSubmissionId="web-ui-task-failed-1",
                clientAppVersion="1.0",
            )
            response, created = runtime.submit(payload)
            self.assertTrue(created)
            runtime.service.store.update_status(
                response.taskId,
                status="failed",
                stage_label="Failed",
                error_code="executor_command_not_found",
                relay_message="Executor command was not found on this machine.",
                error_message="Executor command was not found: openclaw",
            )

            tasks_page = client.get("/ui/tasks")
            self.assertEqual(tasks_page.status_code, 200)
            self.assertIn("Processing command was not found", tasks_page.text)
            self.assertIn("Next: Set the correct command path in Settings.", tasks_page.text)

    def test_web_ui_diagnostics_surfaces_inferred_executor_advice(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base_bootstrap = make_bootstrap(Path(tempdir))
            bootstrap = replace(
                base_bootstrap,
                initial_runtime_config=RuntimeConfig(
                    default_mode="paper_harvest_v1",
                    executor_kind="openclaw",
                    shell_command=base_bootstrap.initial_runtime_config.shell_command,
                    openclaw=replace(
                        base_bootstrap.initial_runtime_config.openclaw,
                        command="definitely_missing_openclaw_command",
                    ),
                ),
            )
            client = TestClient(create_app(bootstrap))

            diagnostics = client.get("/ui/diagnostics")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertIn("Processing command was not found", diagnostics.text)
            self.assertIn("Set the correct command path in Settings.", diagnostics.text)

    def test_web_ui_language_switch_to_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))

            index = client.get("/ui?lang=zh-CN")
            self.assertEqual(index.status_code, 200)
            self.assertIn("本地转发助手", index.text)
            self.assertIn("概览", index.text)
            self.assertIn("近期任务", index.text)
            self.assertEqual(index.cookies.get("relay_lang"), "zh-CN")

            settings_page = client.get("/ui/settings", cookies={"relay_lang": "zh-CN"})
            self.assertEqual(settings_page.status_code, 200)
            self.assertIn("设置", settings_page.text)
            self.assertIn("任务默认值", settings_page.text)
            self.assertIn("测试处理方式", settings_page.text)

    def test_web_ui_localizes_dynamic_task_content_in_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            client = TestClient(create_app(bootstrap))
            runtime = client.app.state.runtime
            payload = ShareSubmissionRequest(
                mode="paper_harvest_v1",
                source="wechat_article",
                rawText="https://example.com/bad",
                rawUrl="https://example.com/bad",
                normalizedUrl="https://example.com/bad",
                clientSubmissionId="web-ui-zh-task-1",
                clientAppVersion="1.0",
            )
            response, created = runtime.submit(payload)
            self.assertTrue(created)
            runtime.service.store.update_status(
                response.taskId,
                status="failed",
                stage_label="Failed",
                error_code="executor_command_not_found",
                relay_message="Executor command was not found on this machine.",
                error_message="Executor command was not found: openclaw",
            )

            tasks_page = client.get("/ui/tasks?lang=zh-CN")
            self.assertEqual(tasks_page.status_code, 200)
            self.assertIn("未找到处理命令", tasks_page.text)
            self.assertIn("后续建议：", tasks_page.text)

            detail = client.get(f"/ui/tasks/{response.taskId}?lang=zh-CN")
            self.assertEqual(detail.status_code, 200)
            self.assertIn("后续建议", detail.text)
            self.assertIn("请到设置里填写正确的命令路径。", detail.text)

            diagnostics = client.get("/ui/diagnostics?lang=zh-CN")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertIn("后续建议", diagnostics.text)
