from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.config import (
    BootstrapSettings,
    CustomModeRuntimeConfig,
    OpenClawRuntimeConfig,
    RuntimeConfig,
    ShellCommandRuntimeConfig,
    validate_runtime_config,
)


CONFIG_VERSION = 1


def _merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class RuntimeConfigStore:
    def __init__(self, bootstrap: BootstrapSettings):
        self.bootstrap = bootstrap
        self.path = bootstrap.runtime_config_path

    def load(self) -> RuntimeConfig:
        if not self.path.exists():
            config = self.bootstrap.initial_runtime_config
            self.save(config)
            return config
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw, migrated = self._extract_runtime_dict(raw)
        config = self._from_dict(raw)
        validate_runtime_config(config)
        if migrated:
            self.save(config)
        return config

    def save(self, config: RuntimeConfig) -> None:
        validate_runtime_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "configVersion": CONFIG_VERSION,
            "runtime": config.to_json_dict(),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def merge_and_save(self, updates: dict[str, Any]) -> RuntimeConfig:
        current = self.load()
        merged_dict = _merge_dict(current.to_json_dict(), updates)
        config = self._from_dict(merged_dict)
        self.save(config)
        return config

    def merge_preview(self, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        return _merge_dict(current.to_json_dict(), updates)

    def runtime_from_dict(self, raw: dict[str, Any]) -> RuntimeConfig:
        config = self._from_dict(raw)
        validate_runtime_config(config)
        return config

    def _from_dict(self, raw: dict[str, Any]) -> RuntimeConfig:
        defaults = self.bootstrap.initial_runtime_config.to_json_dict()
        merged = _merge_dict(defaults, raw)
        return RuntimeConfig(
            default_mode=str(merged["default_mode"]).strip() or defaults["default_mode"],
            executor_kind=str(merged["executor_kind"]).strip().lower() or defaults["executor_kind"],
            shell_command=ShellCommandRuntimeConfig(
                template=str(merged["shell_command"].get("template", defaults["shell_command"]["template"])),
                timeout_seconds=int(merged["shell_command"].get("timeout_seconds", defaults["shell_command"]["timeout_seconds"])),
            ),
            openclaw=OpenClawRuntimeConfig(
                command=str(merged["openclaw"].get("command", defaults["openclaw"]["command"])),
                target_mode=str(merged["openclaw"].get("target_mode", defaults["openclaw"]["target_mode"])).strip().lower(),
                local=bool(merged["openclaw"].get("local", defaults["openclaw"]["local"])),
                agent_id=str(merged["openclaw"].get("agent_id", defaults["openclaw"]["agent_id"])),
                session_id=str(merged["openclaw"].get("session_id", defaults["openclaw"]["session_id"])),
                to=str(merged["openclaw"].get("to", defaults["openclaw"]["to"])),
                channel=str(merged["openclaw"].get("channel", defaults["openclaw"]["channel"])),
                thinking=str(merged["openclaw"].get("thinking", defaults["openclaw"]["thinking"])).strip().lower(),
                json_output=bool(merged["openclaw"].get("json_output", defaults["openclaw"]["json_output"])),
                browser_profile=str(merged["openclaw"].get("browser_profile", defaults["openclaw"]["browser_profile"])),
                wechat_use_browser=bool(merged["openclaw"].get("wechat_use_browser", defaults["openclaw"]["wechat_use_browser"])),
                timeout_seconds=int(merged["openclaw"].get("timeout_seconds", defaults["openclaw"]["timeout_seconds"])),
                session_lock_retry_attempts=int(
                    merged["openclaw"].get("session_lock_retry_attempts", defaults["openclaw"]["session_lock_retry_attempts"])
                ),
                session_lock_retry_base_seconds=int(
                    merged["openclaw"].get("session_lock_retry_base_seconds", defaults["openclaw"]["session_lock_retry_base_seconds"])
                ),
                session_lock_defer_cycles=int(
                    merged["openclaw"].get("session_lock_defer_cycles", defaults["openclaw"]["session_lock_defer_cycles"])
                ),
                session_lock_defer_seconds=int(
                    merged["openclaw"].get("session_lock_defer_seconds", defaults["openclaw"]["session_lock_defer_seconds"])
                ),
                network_retry_attempts=int(
                    merged["openclaw"].get("network_retry_attempts", defaults["openclaw"]["network_retry_attempts"])
                ),
                network_retry_base_seconds=int(
                    merged["openclaw"].get("network_retry_base_seconds", defaults["openclaw"]["network_retry_base_seconds"])
                ),
            ),
            custom_modes=tuple(
                CustomModeRuntimeConfig(
                    id=str(item.get("id", "")).strip(),
                    label=str(item.get("label", "")).strip(),
                    description=str(item.get("description", "")).strip(),
                    executor_kind=str(item.get("executor_kind", "shell_command")).strip().lower() or "shell_command",
                    shell_command_template=str(item.get("shell_command_template", "")).strip(),
                    timeout_seconds=int(item.get("timeout_seconds", 180)),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in merged.get("custom_modes", defaults.get("custom_modes", []))
            ),
        )

    def default_json_dict(self) -> dict[str, Any]:
        return asdict(self.bootstrap.initial_runtime_config)

    def current_payload(self) -> dict[str, Any]:
        runtime = self.load()
        return {
            "configVersion": CONFIG_VERSION,
            "runtime": runtime.to_json_dict(),
        }

    def _extract_runtime_dict(self, raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        if "runtime" in raw and isinstance(raw["runtime"], dict):
            return raw["runtime"], bool(raw.get("configVersion") != CONFIG_VERSION)
        return raw, True
