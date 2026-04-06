from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import CustomModeRuntimeConfig
from app.modes import list_client_modes
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
        connection_hints = build_connection_hints(
            runtime.bootstrap.host,
            runtime.bootstrap.port,
            runtime.settings.public_relay_url,
        )
        remote_access_banner = None
        if runtime.bootstrap.host not in {"127.0.0.1", "localhost", "::1"} and not health.get("authConfigured"):
            remote_access_banner = {
                "tone": "warn",
                "title": t("overview.remote_warn_title"),
                "body": t("overview.remote_warn_body"),
            }
        elif (connection_hints.get("private") or connection_hints.get("public")) and health.get("authConfigured"):
            remote_access_banner = {
                "tone": "ok",
                "title": t("overview.remote_ready_title"),
                "body": t("overview.remote_ready_body"),
            }

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
            "connection_hints": connection_hints,
            "remote_access_banner": remote_access_banner,
            "layout_health": health,
            "format_duration_ms": lambda duration_ms: format_duration_ms(duration_ms, lang=lang),
            "format_iso_local": format_iso_local,
            **extra,
        }

    def _settings_context(request: Request, *, saved: bool = False, error: str = "", test_result: dict | None = None, submitted_config=None):
        health = runtime.health_snapshot()
        runtime_config = submitted_config or runtime.runtime_config
        modes = list_client_modes(runtime_config.custom_modes)
        return _base_context(
            request,
            page="settings",
            health=health,
            runtime_config=runtime_config,
            runtime_payload=runtime.config_store.current_payload(),
            runtime_metadata=runtime.config_metadata(),
            modes=modes,
            built_in_modes=[mode for mode in modes if not mode.get("isCustom")],
            custom_modes=runtime_config.custom_modes,
            executors=health["availableExecutors"],
            executor_healths=runtime.executor_healths(),
            saved=saved,
            error=error,
            test_result=test_result,
            mode_test_result=test_result if test_result and test_result.get("modeId") else None,
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

    def _slugify_custom_mode_id(label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
        slug = slug or "mode"
        return f"custom_{slug}"

    def _validate_custom_mode(existing_modes: tuple[CustomModeRuntimeConfig, ...], *, original_id: str, custom_mode: CustomModeRuntimeConfig) -> None:
        built_in_mode_ids = {mode["id"] for mode in list_client_modes() if not mode.get("isCustom")}
        if custom_mode.id in built_in_mode_ids:
            raise ValueError("Custom mode id cannot reuse a built-in mode id.")
        if not re.fullmatch(r"custom_[a-z0-9_]{2,64}", custom_mode.id):
            raise ValueError("Custom mode id must stay lowercase and match custom_[a-z0-9_]+.")
        for mode in existing_modes:
            if mode.id == custom_mode.id and mode.id != original_id:
                raise ValueError("Custom mode id is already being used by another saved custom mode.")
        if not custom_mode.shell_command_template.strip():
            raise ValueError("Custom mode template must not be empty.")
        if custom_mode.timeout_seconds <= 0:
            raise ValueError("Custom mode timeout must be a positive integer.")

    def _duplicate_custom_mode(existing_modes: tuple[CustomModeRuntimeConfig, ...], mode_id: str) -> CustomModeRuntimeConfig:
        source = next((mode for mode in existing_modes if mode.id == mode_id), None)
        if source is None:
            raise ValueError("Custom mode was not found.")
        base_label = source.label.strip() or "Copied Mode"
        base_id = _slugify_custom_mode_id(f"{base_label} copy")
        candidate_id = base_id
        counter = 2
        existing_ids = {mode.id for mode in existing_modes}
        while candidate_id in existing_ids:
            candidate_id = f"{base_id}_{counter}"
            counter += 1
        return replace(
            source,
            id=candidate_id,
            label=f"{base_label} Copy",
        )

    def _parse_custom_mode_form(form: dict[str, list[str]]) -> tuple[str, CustomModeRuntimeConfig, str, str, str]:
        def one(name: str, default: str = "") -> str:
            return form.get(name, [default])[0]

        original_id = one("custom_mode_original_id").strip()
        raw_id = one("custom_mode_id").strip().lower()
        label = one("custom_mode_label").strip()
        if not label:
            raise ValueError("Custom mode name must not be empty.")
        mode_id = raw_id or _slugify_custom_mode_id(label)
        custom_mode = CustomModeRuntimeConfig(
            id=mode_id,
            label=label,
            description=one("custom_mode_description").strip(),
            executor_kind="shell_command",
            shell_command_template=one("custom_mode_shell_command_template"),
            timeout_seconds=int(one("custom_mode_timeout_seconds", "180") or "180"),
            enabled=True,
        )
        return (
            original_id,
            custom_mode,
            one("custom_mode_sample_url", "https://example.com/article").strip() or "https://example.com/article",
            one("custom_mode_sample_text").strip(),
            one("custom_mode_sample_source", "unknown").strip() or "unknown",
        )

    def _upsert_custom_mode(existing_modes: tuple[CustomModeRuntimeConfig, ...], *, original_id: str, custom_mode: CustomModeRuntimeConfig) -> tuple[CustomModeRuntimeConfig, ...]:
        updated = []
        replaced = False
        for mode in existing_modes:
            if mode.id == original_id or mode.id == custom_mode.id:
                if not replaced:
                    updated.append(custom_mode)
                    replaced = True
                continue
            updated.append(mode)
        if not replaced:
            updated.append(custom_mode)
        return tuple(updated)

    def _delete_custom_mode(existing_modes: tuple[CustomModeRuntimeConfig, ...], mode_id: str) -> tuple[CustomModeRuntimeConfig, ...]:
        return tuple(mode for mode in existing_modes if mode.id != mode_id)

    def _custom_modes_payload(custom_modes: tuple[CustomModeRuntimeConfig, ...]) -> list[dict]:
        return [
            {
                "id": mode.id,
                "label": mode.label,
                "description": mode.description,
                "executor_kind": mode.executor_kind,
                "shell_command_template": mode.shell_command_template,
                "timeout_seconds": mode.timeout_seconds,
                "enabled": mode.enabled,
            }
            for mode in custom_modes
        ]

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
            if action in {"save_custom_mode", "test_custom_mode", "delete_custom_mode", "duplicate_custom_mode"}:
                current_config = runtime.runtime_config
                if action == "duplicate_custom_mode":
                    mode_id = (form.get("custom_mode_original_id", [""])[0] or form.get("custom_mode_id", [""])[0]).strip()
                    duplicated_mode = _duplicate_custom_mode(current_config.custom_modes, mode_id)
                    updated_modes = current_config.custom_modes + (duplicated_mode,)
                    await runtime.update_runtime_config({"custom_modes": _custom_modes_payload(updated_modes)})
                    return RedirectResponse(page_url("/ui/settings", lang, saved="1"), status_code=303)
                if action == "delete_custom_mode":
                    mode_id = (form.get("custom_mode_original_id", [""])[0] or form.get("custom_mode_id", [""])[0]).strip()
                    updated_modes = _delete_custom_mode(current_config.custom_modes, mode_id)
                    updates = {"custom_modes": _custom_modes_payload(updated_modes)}
                    if current_config.default_mode == mode_id:
                        updates["default_mode"] = "link_only_v1"
                    await runtime.update_runtime_config(updates)
                    return RedirectResponse(page_url("/ui/settings", lang, saved="1"), status_code=303)

                original_id, custom_mode, sample_url, sample_text, sample_source = _parse_custom_mode_form(form)
                _validate_custom_mode(current_config.custom_modes, original_id=original_id, custom_mode=custom_mode)
                updated_modes = _upsert_custom_mode(current_config.custom_modes, original_id=original_id, custom_mode=custom_mode)
                preview_config = replace(current_config, custom_modes=updated_modes)

                if action == "test_custom_mode":
                    preview = await runtime.test_custom_mode_preview(
                        custom_mode,
                        normalized_url=sample_url,
                        raw_text=sample_text,
                        source=sample_source,
                    )
                    return _template_response(
                        request,
                        "settings.html",
                        _settings_context(
                            request,
                            saved=False,
                            test_result=preview,
                            submitted_config=preview_config,
                        ),
                    )

                await runtime.update_runtime_config({"custom_modes": _custom_modes_payload(updated_modes)})
                return RedirectResponse(page_url("/ui/settings", lang, saved="1"), status_code=303)

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
