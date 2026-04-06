from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cli
from app.config import BootstrapSettings, OpenClawRuntimeConfig, RuntimeConfig, ShellCommandRuntimeConfig
from app.runtime_state import AppRuntime
from app.models import ShareSubmissionRequest


def make_bootstrap(root: Path) -> BootstrapSettings:
    workspace_dir = root / "runtime"
    data_dir = workspace_dir / "data"
    tasks_dir = workspace_dir / "tasks"
    logs_dir = workspace_dir / "logs"
    for directory in (workspace_dir, data_dir, tasks_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return BootstrapSettings(
        host="0.0.0.0",
        port=18080,
        auth_token="cli-test-token",
        service_name="Relay CLI Test",
        service_version="1.0.0",
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


class CliTests(unittest.TestCase):
    def _run_cli(self, bootstrap: BootstrapSettings, argv: list[str]) -> str:
        buffer = io.StringIO()
        with patch.object(cli, "load_bootstrap_settings", return_value=bootstrap):
            with redirect_stdout(buffer):
                exit_code = cli.main(argv)
        self.assertEqual(exit_code, 0)
        return buffer.getvalue()

    def test_init_and_config_show_emit_versioned_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            output = self._run_cli(bootstrap, ["init"])
            self.assertIn("Relay initialized.", output)
            self.assertIn("Config version: v1", output)

            json_output = self._run_cli(bootstrap, ["config", "show", "--json"])
            payload = json.loads(json_output)
            self.assertEqual(payload["configVersion"], 1)
            self.assertEqual(payload["runtime"]["executor_kind"], "mock")

    def test_doctor_and_tasks_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            runtime = AppRuntime(bootstrap)
            payload = ShareSubmissionRequest(
                mode="paper_harvest_v1",
                source="wechat_article",
                rawText="https://example.com/article",
                rawUrl="https://example.com/article",
                normalizedUrl="https://example.com/article",
                clientSubmissionId="cli-task-1",
                clientAppVersion="1.0",
            )
            response, created = runtime.submit(payload)
            self.assertTrue(created)

            doctor_json = self._run_cli(bootstrap, ["doctor", "--json"])
            doctor_payload = json.loads(doctor_json)
            self.assertIn("checks", doctor_payload)
            doctor_short = self._run_cli(bootstrap, ["doctor", "--short"])
            self.assertEqual(doctor_short.strip(), "ready")
            doctor_hints = self._run_cli(bootstrap, ["doctor", "--fix-hints"])
            self.assertIn("No fixes needed. Relay is ready.", doctor_hints)
            doctor_summary = self._run_cli(bootstrap, ["doctor", "--summary"])
            self.assertIn("Overall Status: ok", doctor_summary)

            list_output = self._run_cli(bootstrap, ["tasks", "list"])
            self.assertIn(response.taskId, list_output)

            show_json = self._run_cli(bootstrap, ["tasks", "show", response.taskId, "--json"])
            show_payload = json.loads(show_json)
            self.assertEqual(show_payload["taskId"], response.taskId)

            cancel_output = self._run_cli(bootstrap, ["tasks", "cancel", response.taskId])
            self.assertTrue("cancelled" in cancel_output.lower() or "cancelling" in cancel_output.lower())

    def test_start_uses_uvicorn(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            buffer = io.StringIO()
            with patch.object(cli, "load_bootstrap_settings", return_value=bootstrap):
                with patch.object(cli, "configure_logging") as mock_logging:
                    with patch.object(cli.uvicorn, "run") as mock_run:
                        with redirect_stdout(buffer):
                            exit_code = cli.main(["start", "--host", "127.0.0.1", "--port", "19090"])
            self.assertEqual(exit_code, 0)
            mock_logging.assert_called_once()
            mock_run.assert_called_once()
            output = buffer.getvalue()
            self.assertIn("Relay started.", output)
            self.assertIn("Executor: mock", output)
            self.assertIn("Default mode: paper_harvest_v1", output)

    def test_smoke_commands_return_structured_results(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))

            mock_output = self._run_cli(bootstrap, ["smoke", "mock", "--json"])
            mock_payload = json.loads(mock_output)
            self.assertEqual(mock_payload["kind"], "mock")
            self.assertEqual(mock_payload["status"], "completed")
            self.assertIn("task", mock_payload)

            shell_output = self._run_cli(bootstrap, ["smoke", "shell", "--json"])
            shell_payload = json.loads(shell_output)
            self.assertEqual(shell_payload["kind"], "shell")
            self.assertEqual(shell_payload["status"], "completed")
            self.assertIn("shell-smoke-ok", shell_payload["task"]["resultSummary"])

    def test_config_validate_reports_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            text_output = self._run_cli(bootstrap, ["config", "validate"])
            self.assertIn("Runtime config is valid.", text_output)

            json_output = self._run_cli(bootstrap, ["config", "validate", "--json"])
            payload = json.loads(json_output)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["executorKind"], "mock")

    def test_legacy_run_entry_defaults_to_start_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_path = Path(__file__).resolve().parents[1] / "run.py"
            with patch("sys.argv", ["run.py"]):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    namespace: dict[str, object] = {"__name__": "__main__", "__file__": str(run_path)}
                    with self.assertRaises(SystemExit) as exit_info:
                        exec(run_path.read_text(encoding="utf-8"), namespace)
            self.assertEqual(exit_info.exception.code, 0)
            called_command = mock_run.call_args.args[0]
            self.assertEqual(called_command[:3], [sys.executable, "-m", "relay"])
            self.assertEqual(called_command[3:], ["start"])
