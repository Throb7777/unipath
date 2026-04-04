from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.user_facing import infer_health_advice


@dataclass(frozen=True)
class DiagnosticItem:
    key: str
    category: str
    severity: str
    title: str
    message: str
    suggested_actions: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticReport:
    status: str
    summary: str
    items: tuple[DiagnosticItem, ...]
    blockers: tuple[DiagnosticItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "items": [asdict(item) for item in self.items],
            "blockers": [asdict(item) for item in self.blockers],
            "sections": group_diagnostic_items(self.items),
        }


def build_runtime_diagnostic_report(
    *,
    workspace_dir: str,
    database_path: str,
    health: dict[str, Any],
    executor_healths: list[Any],
) -> DiagnosticReport:
    items: list[DiagnosticItem] = []

    runtime_ok = bool(health.get("runtimeWritable"))
    items.append(
        DiagnosticItem(
            key="runtime_directory",
            category="runtime",
            severity="ok" if runtime_ok else "blocked",
            title="Runtime directory is ready" if runtime_ok else "Runtime directory is not writable",
            message=workspace_dir,
            suggested_actions=() if runtime_ok else (
                "Check WORKSPACE_DIR and make sure the relay process can write to it.",
            ),
        )
    )

    db_ok = bool(health.get("databaseReady"))
    items.append(
        DiagnosticItem(
            key="database_ready",
            category="runtime",
            severity="ok" if db_ok else "blocked",
            title="Database is ready" if db_ok else "Database is not ready",
            message=database_path,
            suggested_actions=() if db_ok else (
                "Make sure the runtime data directory exists and that no other process is locking relay.sqlite3.",
            ),
        )
    )

    web_ui_enabled = bool(health.get("webUiEnabled"))
    items.append(
        DiagnosticItem(
            key="web_ui_enabled",
            category="config",
            severity="ok" if web_ui_enabled else "warning",
            title="Web UI is enabled" if web_ui_enabled else "Web UI is disabled",
            message=f"local_only={health.get('webUiLocalOnly')}",
            suggested_actions=() if web_ui_enabled else (
                "Enable WEB_UI_ENABLED if you want to manage relay from the browser.",
            ),
        )
    )

    configured_executor = str(health.get("configuredExecutor", "") or "")
    executor_available = bool(health.get("executorAvailable"))
    executor_message = str(health.get("executorMessage", "") or "")
    inferred = infer_health_advice(
        configured_executor=configured_executor,
        executor_available=executor_available,
        executor_message=executor_message,
    )
    items.append(
        DiagnosticItem(
            key="configured_executor",
            category="executor",
            severity="ok" if executor_available else "warning",
            title="Processing method looks ready" if executor_available else (inferred.title if inferred else "Selected processing method needs setup"),
            message=executor_message or configured_executor,
            suggested_actions=inferred.suggested_actions if inferred else (),
            details={"executor": configured_executor},
        )
    )

    supported_default_modes = set(health.get("supportedDefaultModes") or [])
    default_mode = str(health.get("defaultMode", "") or "")
    mode_ok = not supported_default_modes or default_mode in supported_default_modes
    items.append(
        DiagnosticItem(
            key="default_mode",
            category="config",
            severity="ok" if mode_ok else "warning",
            title="Default mode is compatible" if mode_ok else "Default mode does not match the selected processing method",
            message=default_mode or "-",
            suggested_actions=() if mode_ok else (
                "Open Settings and switch to a mode supported by the selected processing method.",
            ),
            details={"supportedModes": sorted(supported_default_modes)},
        )
    )

    for health_item in executor_healths:
        available = bool(getattr(health_item, "available", False))
        is_configured = health_item.executorId == configured_executor
        severity = "ok" if available or not is_configured else "warning"
        title = (
            f"{health_item.label} is ready"
            if available
            else (f"{health_item.label} needs setup" if is_configured else f"{health_item.label} is optional")
        )
        items.append(
            DiagnosticItem(
                key=f"executor:{health_item.executorId}",
                category="executor",
                severity=severity,
                title=title,
                message=health_item.message or health_item.label,
                details=getattr(health_item, "details", {}) or {},
            )
        )

    blockers = tuple(item for item in items if item.severity in {"warning", "blocked"})
    status = "ok"
    if any(item.severity == "blocked" for item in items):
        status = "blocked"
    elif blockers:
        status = "warning"

    summary = {
        "ok": "Relay is ready.",
        "warning": "Relay is running with setup warnings.",
        "blocked": "Relay is blocked by an environment issue.",
    }[status]

    return DiagnosticReport(
        status=status,
        summary=summary,
        items=tuple(items),
        blockers=blockers,
    )


def build_environment_diagnostic_summary(
    *,
    service_name: str,
    service_version: str,
    health: dict[str, Any],
    report: DiagnosticReport,
    runtime_config_path: str,
) -> str:
    lines = [
        f"Service: {service_name} {service_version}",
        f"Overall Status: {report.status}",
        f"Summary: {report.summary}",
        f"Processing Method: {health.get('configuredExecutor') or '-'}",
        f"Default Mode: {health.get('defaultMode') or '-'}",
        f"Runtime Config: {runtime_config_path}",
    ]
    if report.blockers:
        lines.append("Current Blockers:")
        for item in report.blockers[:3]:
            lines.append(f"- {item.title}: {item.message}")
            for action in item.suggested_actions[:2]:
                lines.append(f"  Next: {action}")
    else:
        lines.append("Current Blockers: none")
        lines.append("Next: Submit a smoke test or a real task.")
    return "\n".join(lines)


def group_diagnostic_items(items: tuple[DiagnosticItem, ...]) -> list[dict[str, Any]]:
    labels = {
        "runtime": "Runtime",
        "config": "Configuration",
        "executor": "Processing Method",
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(asdict(item))
    return [
        {
            "key": category,
            "label": labels.get(category, category.title()),
            "items": grouped[category],
        }
        for category in ("runtime", "config", "executor")
        if category in grouped
    ]
