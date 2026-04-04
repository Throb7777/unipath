from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import uvicorn

from app.config import BootstrapSettings, load_bootstrap_settings
from app.http_app import create_app
from app.logging_setup import configure_logging
from app.runtime_state import AppRuntime
from app.web.view_models import build_connection_hints, collect_task_artifacts, format_duration_ms, format_iso_local


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relay", description="Local relay companion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize runtime files and default config")
    init_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    doctor_parser = subparsers.add_parser("doctor", help="Run local relay diagnostics")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")
    doctor_parser.add_argument("--short", action="store_true", help="Print a one-line diagnosis summary")
    doctor_parser.add_argument("--fix-hints", action="store_true", help="Print suggested next steps for warnings")
    doctor_parser.add_argument("--summary", action="store_true", help="Print the environment diagnostic summary")

    start_parser = subparsers.add_parser("start", help="Start the relay HTTP service")
    start_parser.add_argument("--host", help="Override bootstrap host")
    start_parser.add_argument("--port", type=int, help="Override bootstrap port")

    status_parser = subparsers.add_parser("status", help="Show local runtime and recent task status")
    status_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    config_parser = subparsers.add_parser("config", help="Inspect runtime configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_show = config_subparsers.add_parser("show", help="Show merged runtime config")
    config_show.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")
    config_subparsers.add_parser("path", help="Show runtime config file path")
    config_validate = config_subparsers.add_parser("validate", help="Validate the current runtime config")
    config_validate.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    tasks_parser = subparsers.add_parser("tasks", help="Inspect or cancel tasks")
    tasks_subparsers = tasks_parser.add_subparsers(dest="tasks_command", required=True)

    tasks_list = tasks_subparsers.add_parser("list", help="List recent tasks")
    tasks_list.add_argument("--limit", type=int, default=20)
    tasks_list.add_argument("--status")
    tasks_list.add_argument("--executor")
    tasks_list.add_argument("--source")
    tasks_list.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    tasks_show = tasks_subparsers.add_parser("show", help="Show one task")
    tasks_show.add_argument("task_id")
    tasks_show.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    tasks_cancel = tasks_subparsers.add_parser("cancel", help="Request cancellation for one task")
    tasks_cancel.add_argument("task_id")
    tasks_cancel.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    ui_parser = subparsers.add_parser("ui", help="Print the local Web UI address")
    ui_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    smoke_parser = subparsers.add_parser("smoke", help="Run a minimal smoke test")
    smoke_parser.add_argument("kind", choices=["mock", "shell", "openclaw"])
    smoke_parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        return _cmd_init(args.as_json)
    if args.command == "doctor":
        return _cmd_doctor(args.as_json, args.short, args.fix_hints, args.summary)
    if args.command == "start":
        return _cmd_start(args.host, args.port)
    if args.command == "status":
        return _cmd_status(args.as_json)
    if args.command == "config":
        if args.config_command == "show":
            return _cmd_config_show(args.as_json)
        if args.config_command == "path":
            return _cmd_config_path()
        if args.config_command == "validate":
            return _cmd_config_validate(args.as_json)
    if args.command == "tasks":
        if args.tasks_command == "list":
            return _cmd_tasks_list(args.limit, args.status, args.executor, args.source, args.as_json)
        if args.tasks_command == "show":
            return _cmd_tasks_show(args.task_id, args.as_json)
        if args.tasks_command == "cancel":
            return _cmd_tasks_cancel(args.task_id, args.as_json)
    if args.command == "ui":
        return _cmd_ui(args.as_json)
    if args.command == "smoke":
        return _cmd_smoke(args.kind, args.as_json)
    return 1


def _bootstrap() -> BootstrapSettings:
    return load_bootstrap_settings()


def _runtime() -> AppRuntime:
    return AppRuntime(_bootstrap())


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _cmd_init(as_json: bool) -> int:
    bootstrap = _bootstrap()
    runtime_store = AppRuntime(bootstrap).config_store
    payload = runtime_store.current_payload()
    hints = build_connection_hints(bootstrap.host, bootstrap.port)
    result = {
        "status": "ok",
        "workspaceDir": str(bootstrap.workspace_dir),
        "runtimeConfigPath": str(bootstrap.runtime_config_path),
        "webUi": f"{hints['local']}/ui" if bootstrap.web_ui_enabled else "",
        "androidEmulator": hints["android_emulator"],
        "bind": hints["bind"],
    }
    if as_json:
        _print_json(result)
        return 0
    print("Relay initialized.")
    print(f"Workspace: {bootstrap.workspace_dir}")
    print(f"Runtime config: {bootstrap.runtime_config_path}")
    print(f"Config version: v{payload['configVersion']}")
    if bootstrap.web_ui_enabled:
        print(f"Web UI: {hints['local']}/ui")
    print(f"Android emulator base URL: {hints['android_emulator']}")
    print("Next steps: relay doctor, then relay start")
    return 0


def _doctor_payload(runtime: AppRuntime) -> dict[str, Any]:
    health = runtime.health_snapshot()
    report = runtime.diagnostic_report()
    payload = {
        "status": report["status"],
        "checks": [
            {
                "name": item["key"],
                "ok": item["severity"] == "ok",
                "message": item["message"],
                "title": item["title"],
                "category": item["category"],
                "severity": item["severity"],
                "suggestedActions": item["suggested_actions"],
            }
            for item in report["items"]
        ],
        "blockers": report["blockers"],
        "sections": _group_checks(report["items"]),
        "health": health,
        "summary": report["summary"],
        "environmentSummary": runtime.environment_diagnostic_summary(),
    }
    return payload


def _doctor_fix_hints(payload: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for item in payload.get("blockers", []):
        for action in item.get("suggested_actions", []):
            if action not in hints:
                hints.append(action)
    if not hints and payload["status"] == "ok":
        hints.append("No fixes needed. Relay is ready.")
    return hints


def _cmd_doctor(as_json: bool, short: bool, fix_hints: bool, summary_only: bool) -> int:
    runtime = _runtime()
    payload = _doctor_payload(runtime)
    if as_json:
        _print_json(payload)
        return 0
    if summary_only:
        print(payload["environmentSummary"])
        return 0
    if short:
        summary = {
            "ok": "ready",
            "warning": f"warning: {payload['health']['configuredExecutor']} needs attention",
            "blocked": "blocked: relay runtime is not ready",
        }
        print(summary[payload["status"]])
        return 0
    print(f"Overall status: {payload['status']}")
    print(payload["summary"])
    for section in payload["sections"]:
        print(f"{section['title']}:")
        for item in section["items"]:
            prefix = {
                "ok": "[OK]",
                "warning": "[WARN]",
                "blocked": "[BLOCKED]",
            }[item["severity"]]
            print(f"{prefix} {item['title']}: {item['message']}")
    if fix_hints:
        print("Suggested next steps:")
        for hint in _doctor_fix_hints(payload):
            print(f"- {hint}")
    print("Environment diagnostic summary:")
    print(payload["environmentSummary"])
    print(f"Relay UI: {build_connection_hints(runtime.bootstrap.host, runtime.bootstrap.port)['local']}/ui")
    return 0


def _cmd_start(host_override: str | None, port_override: int | None) -> int:
    bootstrap = _bootstrap()
    runtime = AppRuntime(bootstrap)
    configure_logging(bootstrap)
    app = create_app(bootstrap)
    host = host_override or bootstrap.host
    port = port_override or bootstrap.port
    hints = build_connection_hints(host, port)
    print("Relay started.")
    print(f"API: {hints['local']}")
    if bootstrap.web_ui_enabled:
        print(f"Web UI: {hints['local']}/ui")
    print(f"Android emulator: {hints['android_emulator']}")
    print(f"Executor: {runtime.runtime_config.executor_kind}")
    print(f"Default mode: {runtime.runtime_config.default_mode}")
    print(f"Runtime config: {bootstrap.runtime_config_path}")
    uvicorn.run(app, host=host, port=port, reload=False)
    return 0


def _cmd_status(as_json: bool) -> int:
    runtime = _runtime()
    health = runtime.health_snapshot()
    tasks = [task.to_status_response() for task in runtime.list_tasks(limit=5)]
    payload = {"health": health, "recentTasks": [json.loads(task.model_dump_json()) for task in tasks]}
    if as_json:
        _print_json(payload)
        return 0
    print(f"Relay: {health['status']}")
    print(f"Executor: {health['configuredExecutor']}")
    print(f"Default mode: {health['defaultMode']}")
    print(f"Runtime config: {health['runtimeConfigPath']}")
    if tasks:
        print("Recent tasks:")
        for task in tasks:
            print(f"- {task.taskId} | {task.stageLabel} | {format_duration_ms(task.durationMs)} | {format_iso_local(task.updatedAt)}")
    else:
        print("Recent tasks: none")
    return 0


def _cmd_config_show(as_json: bool) -> int:
    runtime = _runtime()
    payload = runtime.config_store.current_payload()
    if as_json:
        _print_json(payload)
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_config_path() -> int:
    print(str(_bootstrap().runtime_config_path))
    return 0


def _cmd_config_validate(as_json: bool) -> int:
    runtime = _runtime()
    payload = {
        "status": "ok",
        "runtimeConfigPath": str(runtime.bootstrap.runtime_config_path),
        "configVersion": runtime.config_store.current_payload()["configVersion"],
        "executorKind": runtime.runtime_config.executor_kind,
        "defaultMode": runtime.runtime_config.default_mode,
        "message": "Runtime config is valid.",
    }
    if as_json:
        _print_json(payload)
        return 0
    print("Runtime config is valid.")
    print(f"Path: {payload['runtimeConfigPath']}")
    print(f"Executor: {payload['executorKind']}")
    print(f"Default mode: {payload['defaultMode']}")
    return 0


def _cmd_tasks_list(limit: int, status: str | None, executor: str | None, source: str | None, as_json: bool) -> int:
    runtime = _runtime()
    tasks = [task.to_status_response() for task in runtime.list_tasks(limit=limit, status=status or None, executor_kind=executor or None, source=source or None)]
    if as_json:
        _print_json([json.loads(task.model_dump_json()) for task in tasks])
        return 0
    if not tasks:
        print("No tasks matched.")
        return 0
    for task in tasks:
        print(f"{task.taskId} | {task.stageLabel} | {task.executorKind} | {format_duration_ms(task.durationMs)} | {format_iso_local(task.updatedAt)}")
    return 0


def _cmd_tasks_show(task_id: str, as_json: bool) -> int:
    runtime = _runtime()
    task = runtime.get_task_status(task_id)
    payload = json.loads(task.model_dump_json())
    payload["artifacts"] = collect_task_artifacts(task.taskDir)
    if as_json:
        _print_json(payload)
        return 0
    print(f"Task: {task.taskId}")
    print(f"Status: {task.stageLabel}")
    print(f"Executor: {task.executorKind}")
    print(f"Mode: {task.mode}")
    print(f"Duration: {format_duration_ms(task.durationMs)}")
    print(f"Updated: {format_iso_local(task.updatedAt)}")
    print(f"Task dir: {task.taskDir}")
    if payload["artifacts"]:
        print("Artifacts:")
        for artifact in payload["artifacts"]:
            print(f"  - {artifact['name']}: {artifact['path']}")
    print("Summary:")
    print(task.resultSummary or task.errorMessage or task.relayMessage or "-")
    if task.problemTitle:
        print(f"Problem: {task.problemTitle}")
    if task.suggestedActions:
        print("Suggested next steps:")
        for item in task.suggestedActions:
            print(f"- {item}")
    print("Diagnostic summary:")
    print(task.diagnosticSummary)
    return 0


def _cmd_tasks_cancel(task_id: str, as_json: bool) -> int:
    runtime = _runtime()
    response = runtime.cancel_task(task_id)
    payload = json.loads(response.model_dump_json())
    if as_json:
        _print_json(payload)
        return 0
    print(f"{response.status}: {response.message}")
    return 0


def _cmd_ui(as_json: bool) -> int:
    bootstrap = _bootstrap()
    hints = build_connection_hints(bootstrap.host, bootstrap.port)
    payload = {"url": f"{hints['local']}/ui", "enabled": bootstrap.web_ui_enabled}
    if as_json:
        _print_json(payload)
        return 0
    if bootstrap.web_ui_enabled:
        print(f"{hints['local']}/ui")
    else:
        print("Web UI is disabled.")
    return 0


def _cmd_smoke(kind: str, as_json: bool) -> int:
    runtime = _runtime()
    payload = asyncio.run(runtime.smoke_test(kind))
    if as_json:
        _print_json(payload)
        return 0
    print(f"Smoke kind: {payload['kind']}")
    print(f"Status: {payload['status']}")
    print(f"Summary: {payload['summary']}")
    if "task" in payload:
        task = payload["task"]
        print(f"Task ID: {task['taskId']}")
        print(f"Stage: {task['stageLabel']}")
        if task.get("suggestedActions"):
            print("Suggested next steps:")
            for item in task["suggestedActions"]:
                print(f"- {item}")
    else:
        print(payload["health"].get("executorMessage", ""))
    return 0


def _group_checks(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    titles = {
        "runtime": "Runtime",
        "config": "Configuration",
        "executor": "Processing Method",
    }
    grouped: list[dict[str, Any]] = []
    for category in ("runtime", "config", "executor"):
        category_items = [item for item in items if item["category"] == category]
        if category_items:
            grouped.append({"key": category, "title": titles[category], "items": category_items})
    return grouped


if __name__ == "__main__":
    raise SystemExit(main())
