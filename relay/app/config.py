from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from app.openclaw_support import VALID_OPENCLAW_TARGET_MODES, VALID_THINKING_LEVELS


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _parse_bool(value: str, default: bool) -> bool:
    raw = value.strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OpenClawRuntimeConfig:
    command: str
    target_mode: str
    local: bool
    agent_id: str
    session_id: str
    to: str
    channel: str
    thinking: str
    json_output: bool
    browser_profile: str
    wechat_use_browser: bool
    timeout_seconds: int
    session_lock_retry_attempts: int
    session_lock_retry_base_seconds: int
    session_lock_defer_cycles: int
    session_lock_defer_seconds: int
    network_retry_attempts: int
    network_retry_base_seconds: int


@dataclass(frozen=True)
class ShellCommandRuntimeConfig:
    template: str
    timeout_seconds: int


@dataclass(frozen=True)
class CustomModeRuntimeConfig:
    id: str
    label: str
    description: str
    executor_kind: str
    shell_command_template: str
    timeout_seconds: int
    enabled: bool = True


@dataclass(frozen=True)
class RuntimeConfig:
    default_mode: str
    executor_kind: str
    shell_command: ShellCommandRuntimeConfig
    openclaw: OpenClawRuntimeConfig
    custom_modes: tuple[CustomModeRuntimeConfig, ...] = ()

    def to_json_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BootstrapSettings:
    host: str
    port: int
    auth_token: str
    service_name: str
    service_version: str
    workspace_dir: Path
    data_dir: Path
    tasks_dir: Path
    logs_dir: Path
    database_path: Path
    runtime_config_path: Path
    web_ui_enabled: bool
    web_ui_local_only: bool
    initial_runtime_config: RuntimeConfig
    public_relay_url: str = ""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    auth_token: str
    public_relay_url: str
    service_name: str
    service_version: str
    default_mode: str
    executor_kind: str
    shell_command_template: str
    shell_command_timeout_seconds: int
    openclaw_command: str
    openclaw_target_mode: str
    openclaw_local: bool
    openclaw_agent_id: str
    openclaw_session_id: str
    openclaw_to: str
    openclaw_channel: str
    openclaw_thinking: str
    openclaw_json_output: bool
    openclaw_browser_profile: str
    openclaw_wechat_use_browser: bool
    openclaw_timeout_seconds: int
    openclaw_session_lock_retry_attempts: int
    openclaw_session_lock_retry_base_seconds: int
    openclaw_session_lock_defer_cycles: int
    openclaw_session_lock_defer_seconds: int
    openclaw_network_retry_attempts: int
    openclaw_network_retry_base_seconds: int
    max_concurrent_tasks: int
    startup_recovery_limit: int
    startup_recovery_stagger_ms: int
    task_retention_days: int
    task_result_char_limit: int
    task_error_char_limit: int
    task_file_char_limit: int
    task_cleanup_interval_seconds: int
    task_request_preview_char_limit: int
    task_keep_success_debug_files: bool
    workspace_dir: Path
    data_dir: Path
    tasks_dir: Path
    logs_dir: Path
    database_path: Path
    web_ui_enabled: bool
    web_ui_local_only: bool
    runtime_config_path: Path
    custom_modes: tuple[CustomModeRuntimeConfig, ...] = ()


def load_bootstrap_settings() -> BootstrapSettings:
    project_root = Path(__file__).resolve().parents[1]
    _load_dotenv(project_root / ".env")

    workspace_raw = os.getenv("WORKSPACE_DIR", "./runtime")
    workspace_dir = Path(workspace_raw)
    if not workspace_dir.is_absolute():
        workspace_dir = (project_root / workspace_dir).resolve()

    data_dir = workspace_dir / "data"
    tasks_dir = workspace_dir / "tasks"
    logs_dir = workspace_dir / "logs"
    for directory in (workspace_dir, data_dir, tasks_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    initial_runtime_config = RuntimeConfig(
        default_mode=os.getenv("DEFAULT_MODE", "paper_harvest_v1").strip() or "paper_harvest_v1",
        executor_kind=os.getenv("EXECUTOR_KIND", "openclaw").strip().lower() or "openclaw",
        shell_command=ShellCommandRuntimeConfig(
            template=os.getenv("SHELL_COMMAND_TEMPLATE", "").strip(),
            timeout_seconds=int(os.getenv("SHELL_COMMAND_TIMEOUT_SECONDS", "180")),
        ),
        openclaw=OpenClawRuntimeConfig(
            command=os.getenv("OPENCLAW_COMMAND", "openclaw").strip() or "openclaw",
            target_mode=os.getenv("OPENCLAW_TARGET_MODE", "agent").strip().lower() or "agent",
            local=_parse_bool(os.getenv("OPENCLAW_LOCAL", "true"), default=True),
            agent_id=os.getenv("OPENCLAW_AGENT_ID", "main").strip() or "main",
            session_id=os.getenv("OPENCLAW_SESSION_ID", "").strip(),
            to=os.getenv("OPENCLAW_TO", "").strip(),
            channel=os.getenv("OPENCLAW_CHANNEL", "").strip(),
            thinking=os.getenv("OPENCLAW_THINKING", "").strip().lower(),
            json_output=_parse_bool(os.getenv("OPENCLAW_JSON_OUTPUT", "false"), default=False),
            browser_profile=os.getenv("OPENCLAW_BROWSER_PROFILE", "openclaw").strip() or "openclaw",
            wechat_use_browser=_parse_bool(os.getenv("OPENCLAW_WECHAT_USE_BROWSER", "true"), default=True),
            timeout_seconds=int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "300")),
            session_lock_retry_attempts=int(os.getenv("OPENCLAW_SESSION_LOCK_RETRY_ATTEMPTS", "5")),
            session_lock_retry_base_seconds=int(os.getenv("OPENCLAW_SESSION_LOCK_RETRY_BASE_SECONDS", "3")),
            session_lock_defer_cycles=int(os.getenv("OPENCLAW_SESSION_LOCK_DEFER_CYCLES", "2")),
            session_lock_defer_seconds=int(os.getenv("OPENCLAW_SESSION_LOCK_DEFER_SECONDS", "20")),
            network_retry_attempts=int(os.getenv("OPENCLAW_NETWORK_RETRY_ATTEMPTS", "3")),
            network_retry_base_seconds=int(os.getenv("OPENCLAW_NETWORK_RETRY_BASE_SECONDS", "4")),
        ),
        custom_modes=(),
    )

    bootstrap = BootstrapSettings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        auth_token=os.getenv("AUTH_TOKEN", "").strip(),
        public_relay_url=os.getenv("PUBLIC_RELAY_URL", "").strip(),
        service_name=os.getenv("SERVICE_NAME", "UniPATH Forwarding Service").strip() or "UniPATH Forwarding Service",
        service_version=os.getenv("SERVICE_VERSION", "1.0.0").strip() or "1.0.0",
        workspace_dir=workspace_dir,
        data_dir=data_dir,
        tasks_dir=tasks_dir,
        logs_dir=logs_dir,
        database_path=data_dir / "relay.sqlite3",
        runtime_config_path=data_dir / "config.json",
        web_ui_enabled=_parse_bool(os.getenv("WEB_UI_ENABLED", "true"), default=True),
        web_ui_local_only=_parse_bool(os.getenv("WEB_UI_LOCAL_ONLY", "true"), default=True),
        initial_runtime_config=initial_runtime_config,
    )
    validate_bootstrap_settings(bootstrap)
    validate_runtime_config(initial_runtime_config)
    return bootstrap


def resolve_settings(bootstrap: BootstrapSettings, runtime_config: RuntimeConfig) -> Settings:
    settings = Settings(
        host=bootstrap.host,
        port=bootstrap.port,
        auth_token=bootstrap.auth_token,
        public_relay_url=bootstrap.public_relay_url,
        service_name=bootstrap.service_name,
        service_version=bootstrap.service_version,
        default_mode=runtime_config.default_mode,
        executor_kind=runtime_config.executor_kind,
        shell_command_template=runtime_config.shell_command.template,
        shell_command_timeout_seconds=runtime_config.shell_command.timeout_seconds,
        openclaw_command=runtime_config.openclaw.command,
        openclaw_target_mode=runtime_config.openclaw.target_mode,
        openclaw_local=runtime_config.openclaw.local,
        openclaw_agent_id=runtime_config.openclaw.agent_id,
        openclaw_session_id=runtime_config.openclaw.session_id,
        openclaw_to=runtime_config.openclaw.to,
        openclaw_channel=runtime_config.openclaw.channel,
        openclaw_thinking=runtime_config.openclaw.thinking,
        openclaw_json_output=runtime_config.openclaw.json_output,
        openclaw_browser_profile=runtime_config.openclaw.browser_profile,
        openclaw_wechat_use_browser=runtime_config.openclaw.wechat_use_browser,
        openclaw_timeout_seconds=runtime_config.openclaw.timeout_seconds,
        openclaw_session_lock_retry_attempts=runtime_config.openclaw.session_lock_retry_attempts,
        openclaw_session_lock_retry_base_seconds=runtime_config.openclaw.session_lock_retry_base_seconds,
        openclaw_session_lock_defer_cycles=runtime_config.openclaw.session_lock_defer_cycles,
        openclaw_session_lock_defer_seconds=runtime_config.openclaw.session_lock_defer_seconds,
        openclaw_network_retry_attempts=runtime_config.openclaw.network_retry_attempts,
        openclaw_network_retry_base_seconds=runtime_config.openclaw.network_retry_base_seconds,
        custom_modes=runtime_config.custom_modes,
        max_concurrent_tasks=int(os.getenv("MAX_CONCURRENT_TASKS", "2")),
        startup_recovery_limit=int(os.getenv("STARTUP_RECOVERY_LIMIT", "25")),
        startup_recovery_stagger_ms=int(os.getenv("STARTUP_RECOVERY_STAGGER_MS", "150")),
        task_retention_days=int(os.getenv("TASK_RETENTION_DAYS", "30")),
        task_result_char_limit=int(os.getenv("TASK_RESULT_CHAR_LIMIT", "800")),
        task_error_char_limit=int(os.getenv("TASK_ERROR_CHAR_LIMIT", "1200")),
        task_file_char_limit=int(os.getenv("TASK_FILE_CHAR_LIMIT", "12000")),
        task_cleanup_interval_seconds=int(os.getenv("TASK_CLEANUP_INTERVAL_SECONDS", "43200")),
        task_request_preview_char_limit=int(os.getenv("TASK_REQUEST_PREVIEW_CHAR_LIMIT", "2000")),
        task_keep_success_debug_files=_parse_bool(os.getenv("TASK_KEEP_SUCCESS_DEBUG_FILES", "false"), default=False),
        workspace_dir=bootstrap.workspace_dir,
        data_dir=bootstrap.data_dir,
        tasks_dir=bootstrap.tasks_dir,
        logs_dir=bootstrap.logs_dir,
        database_path=bootstrap.database_path,
        web_ui_enabled=bootstrap.web_ui_enabled,
        web_ui_local_only=bootstrap.web_ui_local_only,
        runtime_config_path=bootstrap.runtime_config_path,
    )
    validate_settings(settings)
    return settings


def load_settings() -> Settings:
    bootstrap = load_bootstrap_settings()
    return resolve_settings(bootstrap, bootstrap.initial_runtime_config)


def validate_bootstrap_settings(settings: BootstrapSettings) -> None:
    if not settings.host.strip():
        raise ValueError("HOST must not be empty.")
    if settings.port <= 0 or settings.port > 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    if not settings.service_name.strip():
        raise ValueError("SERVICE_NAME must not be empty.")
    if not settings.service_version.strip():
        raise ValueError("SERVICE_VERSION must not be empty.")


def validate_runtime_config(runtime_config: RuntimeConfig) -> None:
    import re

    from app.modes import mode_map

    available_modes = mode_map(runtime_config.custom_modes)
    if runtime_config.default_mode not in available_modes:
        raise ValueError(f"default_mode is not registered: {runtime_config.default_mode}")
    if runtime_config.executor_kind not in {"mock", "openclaw", "shell_command"}:
        raise ValueError("executor_kind must be one of: mock, openclaw, shell_command.")
    if runtime_config.shell_command.timeout_seconds <= 0:
        raise ValueError("shell_command.timeout_seconds must be a positive integer.")
    if runtime_config.openclaw.timeout_seconds <= 0:
        raise ValueError("openclaw.timeout_seconds must be a positive integer.")
    if runtime_config.openclaw.session_lock_retry_attempts <= 0 or runtime_config.openclaw.session_lock_retry_base_seconds <= 0:
        raise ValueError("openclaw.session_lock_retry_* settings must be positive integers.")
    if runtime_config.openclaw.session_lock_defer_cycles < 0 or runtime_config.openclaw.session_lock_defer_seconds <= 0:
        raise ValueError("openclaw.session_lock_defer_* settings must be non-negative / positive integers.")
    if runtime_config.openclaw.network_retry_attempts <= 0 or runtime_config.openclaw.network_retry_base_seconds <= 0:
        raise ValueError("openclaw.network_retry_* settings must be positive integers.")
    if runtime_config.executor_kind == "openclaw" and not runtime_config.openclaw.command.strip():
        raise ValueError("openclaw.command must not be empty when executor_kind=openclaw.")
    seen_custom_ids: set[str] = set()
    shell_custom_mode_ids: set[str] = set()
    for custom_mode in runtime_config.custom_modes:
        if not re.fullmatch(r"custom_[a-z0-9_]{2,64}", custom_mode.id):
            raise ValueError("custom mode id must match custom_[a-z0-9_]+ and stay lowercase.")
        if custom_mode.id in seen_custom_ids:
            raise ValueError(f"custom mode id is duplicated: {custom_mode.id}")
        seen_custom_ids.add(custom_mode.id)
        if not custom_mode.label.strip():
            raise ValueError(f"custom mode label must not be empty: {custom_mode.id}")
        if custom_mode.executor_kind != "shell_command":
            raise ValueError("custom modes currently support executor_kind=shell_command only.")
        if custom_mode.timeout_seconds <= 0:
            raise ValueError(f"custom mode timeout_seconds must be a positive integer: {custom_mode.id}")
        if not custom_mode.shell_command_template.strip():
            raise ValueError(f"custom mode shell_command_template must not be empty: {custom_mode.id}")
        if custom_mode.enabled:
            shell_custom_mode_ids.add(custom_mode.id)

    shell_mode_uses_custom_template = runtime_config.default_mode in shell_custom_mode_ids
    if runtime_config.executor_kind == "shell_command" and not shell_mode_uses_custom_template and not runtime_config.shell_command.template.strip():
        raise ValueError("shell_command.template must not be empty when executor_kind=shell_command and the default mode is not a custom shell mode.")
    if runtime_config.openclaw.target_mode not in VALID_OPENCLAW_TARGET_MODES:
        raise ValueError(f"openclaw.target_mode must be one of: {', '.join(sorted(VALID_OPENCLAW_TARGET_MODES))}")
    if runtime_config.openclaw.thinking not in VALID_THINKING_LEVELS:
        raise ValueError(f"openclaw.thinking must be one of: {', '.join(filter(None, sorted(VALID_THINKING_LEVELS)))}")
    if runtime_config.executor_kind == "openclaw":
        if not runtime_config.openclaw.browser_profile:
            raise ValueError("openclaw.browser_profile must not be empty when executor_kind=openclaw.")
        if runtime_config.openclaw.target_mode == "agent" and not runtime_config.openclaw.agent_id:
            raise ValueError("openclaw.agent_id is required when openclaw.target_mode=agent.")
        if runtime_config.openclaw.target_mode == "session" and not runtime_config.openclaw.session_id:
            raise ValueError("openclaw.session_id is required when openclaw.target_mode=session.")
        if runtime_config.openclaw.target_mode == "to" and not runtime_config.openclaw.to:
            raise ValueError("openclaw.to is required when openclaw.target_mode=to.")


def validate_settings(settings: Settings) -> None:
    from app.modes import mode_map

    if settings.default_mode not in mode_map(settings.custom_modes):
        raise ValueError(f"DEFAULT_MODE is not registered: {settings.default_mode}")
    if settings.max_concurrent_tasks <= 0:
        raise ValueError("MAX_CONCURRENT_TASKS must be a positive integer.")
    if settings.startup_recovery_limit <= 0:
        raise ValueError("STARTUP_RECOVERY_LIMIT must be a positive integer.")
    if settings.startup_recovery_stagger_ms < 0:
        raise ValueError("STARTUP_RECOVERY_STAGGER_MS must be zero or a positive integer.")
    if settings.task_retention_days <= 0:
        raise ValueError("TASK_RETENTION_DAYS must be a positive integer.")
    if settings.task_result_char_limit <= 0 or settings.task_error_char_limit <= 0 or settings.task_file_char_limit <= 0:
        raise ValueError("TASK_*_CHAR_LIMIT settings must be positive integers.")
    if settings.task_cleanup_interval_seconds <= 0:
        raise ValueError("TASK_CLEANUP_INTERVAL_SECONDS must be a positive integer.")
    if settings.task_request_preview_char_limit <= 0:
        raise ValueError("TASK_REQUEST_PREVIEW_CHAR_LIMIT must be a positive integer.")
    validate_runtime_config(
        RuntimeConfig(
            default_mode=settings.default_mode,
            executor_kind=settings.executor_kind,
            shell_command=ShellCommandRuntimeConfig(
                template=settings.shell_command_template,
                timeout_seconds=settings.shell_command_timeout_seconds,
            ),
            openclaw=OpenClawRuntimeConfig(
                command=settings.openclaw_command,
                target_mode=settings.openclaw_target_mode,
                local=settings.openclaw_local,
                agent_id=settings.openclaw_agent_id,
                session_id=settings.openclaw_session_id,
                to=settings.openclaw_to,
                channel=settings.openclaw_channel,
                thinking=settings.openclaw_thinking,
                json_output=settings.openclaw_json_output,
                browser_profile=settings.openclaw_browser_profile,
                wechat_use_browser=settings.openclaw_wechat_use_browser,
                timeout_seconds=settings.openclaw_timeout_seconds,
                session_lock_retry_attempts=settings.openclaw_session_lock_retry_attempts,
                session_lock_retry_base_seconds=settings.openclaw_session_lock_retry_base_seconds,
                session_lock_defer_cycles=settings.openclaw_session_lock_defer_cycles,
                session_lock_defer_seconds=settings.openclaw_session_lock_defer_seconds,
                network_retry_attempts=settings.openclaw_network_retry_attempts,
                network_retry_base_seconds=settings.openclaw_network_retry_base_seconds,
            ),
            custom_modes=settings.custom_modes,
        )
    )
