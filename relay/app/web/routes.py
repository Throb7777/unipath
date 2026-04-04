from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.runtime_state import AppRuntime
from app.web.i18n import make_translator, normalize_lang, page_url, resolve_lang, switch_lang_url
from app.web.view_models import (
    build_connection_hints,
    collect_task_artifacts,
    format_duration_ms,
    format_iso_local,
    localize_diagnostic_report,
    localize_dynamic_text,
    localize_environment_summary,
    localize_task_status,
    summarize_task_rows,
)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


def create_web_router(runtime: AppRuntime) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    def _ensure_local_access(request: Request) -> None:
        if not runtime.bootstrap.web_ui_local_only:
            return
        host = (request.client.host if request.client else "").lower()
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(status_code=403, detail="Web UI is only available from the local machine.")

    def _template_response(request: Request, template_name: str, context: dict, status_code: int = 200):
        response = templates.TemplateResponse(request, template_name, context, status_code=status_code)
        response.set_cookie("relay_lang", context["lang"], max_age=60 * 60 * 24 * 365, samesite="lax")
        return response

    def _base_context(request: Request, *, page: str, **extra):
        lang = resolve_lang(request)
        t = make_translator(lang)
        health = runtime.health_snapshot()

        def local_page_url(path: str, **params):
            return page_url(path, lang, **params)

        return {
            "request": request,
            "page": page,
            "lang": lang,
            "t": t,
            "page_url": local_page_url,
            "switch_lang_url": lambda target_lang: switch_lang_url(request, target_lang),
            "service_name": runtime.bootstrap.service_name,
            "connection_hints": build_connection_hints(runtime.bootstrap.host, runtime.bootstrap.port),
            "layout_health": health,
            "format_duration_ms": lambda duration_ms: format_duration_ms(duration_ms, lang=lang),
            "format_iso_local": format_iso_local,
            **extra,
        }

    def _settings_context(request: Request, *, saved: bool = False, error: str = "", test_result: dict | None = None, submitted_config=None):
        health = runtime.health_snapshot()
        return _base_context(
            request,
            page="settings",
            health=health,
            runtime_config=submitted_config or runtime.runtime_config,
            runtime_payload=runtime.config_store.current_payload(),
            runtime_metadata=runtime.config_metadata(),
            modes=runtime.client_config().modes,
            executors=health["availableExecutors"],
            executor_healths=runtime.executor_healths(),
            saved=saved,
            error=error,
            test_result=test_result,
        )

    def _parse_settings_form(form: dict[str, list[str]]) -> dict:
        def one(name: str, default: str = "") -> str:
            return form.get(name, [default])[0]

        def checkbox(name: str) -> bool:
            return name in form

        return {
            "default_mode": one("default_mode"),
            "executor_kind": one("executor_kind"),
            "shell_command": {
                "template": one("shell_command_template"),
                "timeout_seconds": int(one("shell_command_timeout_seconds", "180") or "180"),
            },
            "openclaw": {
                "command": one("openclaw_command"),
                "target_mode": one("openclaw_target_mode"),
                "local": checkbox("openclaw_local"),
                "agent_id": one("openclaw_agent_id"),
                "session_id": one("openclaw_session_id"),
                "to": one("openclaw_to"),
                "channel": one("openclaw_channel"),
                "thinking": one("openclaw_thinking"),
                "json_output": checkbox("openclaw_json_output"),
                "browser_profile": one("openclaw_browser_profile"),
                "wechat_use_browser": checkbox("openclaw_wechat_use_browser"),
                "timeout_seconds": int(one("openclaw_timeout_seconds", "300") or "300"),
                "session_lock_retry_attempts": int(one("openclaw_session_lock_retry_attempts", "5") or "5"),
                "session_lock_retry_base_seconds": int(one("openclaw_session_lock_retry_base_seconds", "3") or "3"),
                "session_lock_defer_cycles": int(one("openclaw_session_lock_defer_cycles", "2") or "2"),
                "session_lock_defer_seconds": int(one("openclaw_session_lock_defer_seconds", "20") or "20"),
                "network_retry_attempts": int(one("openclaw_network_retry_attempts", "3") or "3"),
                "network_retry_base_seconds": int(one("openclaw_network_retry_base_seconds", "4") or "4"),
            },
        }

    @router.get("/ui", response_class=HTMLResponse)
    async def ui_index(request: Request):
        _ensure_local_access(request)
        tasks = runtime.list_task_summaries(limit=5)
        return _template_response(
            request,
            "index.html",
            _base_context(
                request,
                page="index",
                health=runtime.health_snapshot(),
                runtime_config=runtime.runtime_config,
                recent_tasks=summarize_task_rows(tasks, lang=resolve_lang(request)),
            ),
        )

    @router.get("/ui/settings", response_class=HTMLResponse)
    async def ui_settings(request: Request):
        _ensure_local_access(request)
        return _template_response(request, "settings.html", _settings_context(request, saved=request.query_params.get("saved") == "1"))

    @router.post("/ui/settings", response_class=HTMLResponse)
    async def ui_settings_save(request: Request):
        _ensure_local_access(request)
        form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
        updates = _parse_settings_form(form)
        action = form.get("_action", ["save"])[0]
        lang = normalize_lang(form.get("lang", [""])[0])

        try:
            if action == "test":
                preview = runtime.test_runtime_config(updates)
                return _template_response(
                    request,
                    "settings.html",
                    _settings_context(
                        request,
                        saved=False,
                        test_result=preview,
                        submitted_config=preview["runtimeConfig"],
                    ),
                )
            await runtime.update_runtime_config(updates)
            if action == "save_test":
                preview = runtime.test_runtime_config({})
                return _template_response(
                    request,
                    "settings.html",
                    _settings_context(
                        request,
                        saved=True,
                        test_result=preview,
                    ),
                )
        except Exception as exc:
            return _template_response(
                request,
                "settings.html",
                _settings_context(request, saved=False, error=str(exc)),
                status_code=400,
            )
        return RedirectResponse(page_url("/ui/settings", lang, saved="1"), status_code=303)

    @router.get("/ui/tasks", response_class=HTMLResponse)
    async def ui_tasks(request: Request):
        _ensure_local_access(request)
        status = request.query_params.get("status") or None
        executor_kind = request.query_params.get("executor") or None
        source = request.query_params.get("source") or None
        tasks = runtime.list_task_summaries(limit=100, status=status, executor_kind=executor_kind, source=source)
        return _template_response(
            request,
            "tasks.html",
            _base_context(
                request,
                page="tasks",
                tasks=summarize_task_rows(tasks, lang=resolve_lang(request)),
                filters={"status": status or "", "executor": executor_kind or "", "source": source or ""},
                executors=runtime.health_snapshot()["availableExecutors"],
            ),
        )

    @router.get("/ui/tasks/{task_id}", response_class=HTMLResponse)
    async def ui_task_detail(request: Request, task_id: str):
        _ensure_local_access(request)
        lang = resolve_lang(request)
        task = localize_task_status(runtime.get_task_status(task_id), lang=lang)
        record = runtime.get_task_record(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return _template_response(
            request,
            "task_detail.html",
            _base_context(
                request,
                page="tasks",
                task=task,
                record=record,
                artifacts=collect_task_artifacts(task.taskDir),
            ),
        )

    @router.post("/ui/tasks/{task_id}/cancel")
    async def ui_task_cancel(request: Request, task_id: str):
        _ensure_local_access(request)
        runtime.cancel_task(task_id)
        return RedirectResponse(page_url(f"/ui/tasks/{task_id}", resolve_lang(request)), status_code=303)

    @router.get("/ui/diagnostics", response_class=HTMLResponse)
    async def ui_diagnostics(request: Request):
        _ensure_local_access(request)
        lang = resolve_lang(request)
        health = runtime.health_snapshot()
        health = {
            **health,
            "status": localize_dynamic_text(str(health.get("status", "")), lang=lang),
            "executorMessage": localize_dynamic_text(str(health.get("executorMessage", "")), lang=lang),
        }
        executor_healths = [
            replace(item, message=localize_dynamic_text(item.message or "", lang=lang))
            for item in runtime.executor_healths()
        ]
        diagnostic_report = localize_diagnostic_report(runtime.diagnostic_report(), lang=lang)
        return _template_response(
            request,
            "diagnostics.html",
            _base_context(
                request,
                page="diagnostics",
                health=health,
                runtime_config=runtime.runtime_config,
                runtime_payload=runtime.config_store.current_payload(),
                runtime_metadata=runtime.config_metadata(),
                executor_healths=executor_healths,
                diagnostic_report=diagnostic_report,
                environment_summary=localize_environment_summary(runtime.environment_diagnostic_summary(), lang=lang),
            ),
        )

    return router
