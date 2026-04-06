from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import (
    BootstrapSettings,
    OpenClawRuntimeConfig,
    RuntimeConfig,
    ShellCommandRuntimeConfig,
    resolve_settings,
)
from app.runtime_config import RuntimeConfigStore
from app.runtime_state import AppRuntime


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
        service_name="Relay Test",
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


class RuntimeConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_config_store_persists_nested_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            store = RuntimeConfigStore(bootstrap)

            config = store.load()
            self.assertEqual(config.executor_kind, "mock")

            updated = store.merge_and_save(
                {
                    "executor_kind": "shell_command",
                    "default_mode": "link_only_v1",
                    "shell_command": {"template": "echo {normalized_url}", "timeout_seconds": 45},
                }
            )

            self.assertEqual(updated.executor_kind, "shell_command")
            self.assertEqual(updated.default_mode, "link_only_v1")
            self.assertEqual(updated.shell_command.template, "echo {normalized_url}")

            saved_payload = json.loads(bootstrap.runtime_config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["configVersion"], 1)
            self.assertEqual(saved_payload["runtime"]["executor_kind"], "shell_command")
            self.assertEqual(saved_payload["runtime"]["shell_command"]["timeout_seconds"], 45)

    async def test_runtime_config_store_persists_custom_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            store = RuntimeConfigStore(bootstrap)

            updated = store.merge_and_save(
                {
                    "default_mode": "custom_save_article",
                    "executor_kind": "shell_command",
                    "custom_modes": [
                        {
                            "id": "custom_save_article",
                            "label": "Save Article",
                            "description": "Run a local article saver.",
                            "executor_kind": "shell_command",
                            "shell_command_template": "python scripts/save.py \"{normalized_url}\"",
                            "timeout_seconds": 90,
                            "enabled": True,
                        }
                    ],
                }
            )

            self.assertEqual(updated.default_mode, "custom_save_article")
            self.assertEqual(len(updated.custom_modes), 1)
            self.assertEqual(updated.custom_modes[0].label, "Save Article")
            self.assertEqual(updated.custom_modes[0].timeout_seconds, 90)

            saved_payload = json.loads(bootstrap.runtime_config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["runtime"]["custom_modes"][0]["id"], "custom_save_article")

    async def test_runtime_config_store_migrates_legacy_flat_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            legacy = {
                "default_mode": "link_only_v1",
                "executor_kind": "shell_command",
                "shell_command": {"template": "echo {normalized_url}", "timeout_seconds": 50},
                "openclaw": bootstrap.initial_runtime_config.to_json_dict()["openclaw"],
            }
            bootstrap.runtime_config_path.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

            store = RuntimeConfigStore(bootstrap)
            config = store.load()

            self.assertEqual(config.executor_kind, "shell_command")
            self.assertEqual(config.default_mode, "link_only_v1")

            migrated = json.loads(bootstrap.runtime_config_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated["configVersion"], 1)
            self.assertEqual(migrated["runtime"]["executor_kind"], "shell_command")

    async def test_app_runtime_reload_applies_new_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            runtime = AppRuntime(bootstrap)
            await runtime.initialize()
            self.assertEqual(runtime.settings.executor_kind, "mock")

            await runtime.update_runtime_config(
                {
                    "executor_kind": "shell_command",
                    "default_mode": "link_only_v1",
                    "shell_command": {"template": "echo {normalized_url}", "timeout_seconds": 60},
                }
            )

            self.assertEqual(runtime.settings.executor_kind, "shell_command")
            self.assertEqual(runtime.settings.default_mode, "link_only_v1")
            self.assertEqual(runtime.settings.shell_command_template, "echo {normalized_url}")
            resolved = resolve_settings(bootstrap, runtime.runtime_config)
            self.assertEqual(resolved.executor_kind, "shell_command")

    async def test_runtime_config_accepts_custom_shell_mode_as_default_without_global_template(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bootstrap = make_bootstrap(Path(tempdir))
            runtime = AppRuntime(bootstrap)
            await runtime.initialize()

            await runtime.update_runtime_config(
                {
                    "default_mode": "custom_archive_article",
                    "executor_kind": "shell_command",
                    "shell_command": {"template": "", "timeout_seconds": 60},
                    "custom_modes": [
                        {
                            "id": "custom_archive_article",
                            "label": "Archive Article",
                            "description": "Archive a shared article locally.",
                            "executor_kind": "shell_command",
                            "shell_command_template": "echo {normalized_url}",
                            "timeout_seconds": 60,
                            "enabled": True,
                        }
                    ],
                }
            )

            self.assertEqual(runtime.settings.default_mode, "custom_archive_article")
            self.assertEqual(runtime.settings.custom_modes[0].id, "custom_archive_article")
