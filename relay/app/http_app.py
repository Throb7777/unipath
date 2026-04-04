from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import BootstrapSettings, load_bootstrap_settings
from app.models import CancelTaskResponse, ClientConfigResponse, ShareSubmissionRequest, ShareSubmissionResponse, TaskStatusResponse
from app.runtime_state import AppRuntime
from app.web.routes import create_web_router


def create_app(bootstrap: BootstrapSettings | None = None) -> FastAPI:
    bootstrap_settings = bootstrap or load_bootstrap_settings()
    runtime = AppRuntime(bootstrap_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.initialize()
        yield
        await runtime.shutdown()

    app = FastAPI(title=bootstrap_settings.service_name, version=bootstrap_settings.service_version, lifespan=lifespan)
    app.state.bootstrap = bootstrap_settings
    app.state.runtime = runtime

    def get_runtime() -> AppRuntime:
        return app.state.runtime

    def verify_auth(authorization: str | None = Header(default=None)) -> None:
        configured_settings: BootstrapSettings = app.state.bootstrap
        if not configured_settings.auth_token:
            return
        expected = f"Bearer {configured_settings.auth_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/api/health")
    def health_check() -> dict:
        return app.state.runtime.health_snapshot()

    @app.get("/api/client-config", response_model=ClientConfigResponse, dependencies=[Depends(verify_auth)])
    def client_config(runtime_state: AppRuntime = Depends(get_runtime)) -> ClientConfigResponse:
        return runtime_state.client_config()

    @app.post("/api/share-submissions", response_model=ShareSubmissionResponse, dependencies=[Depends(verify_auth)])
    def submit_share(
        payload: ShareSubmissionRequest,
        background_tasks: BackgroundTasks,
        runtime_state: AppRuntime = Depends(get_runtime),
    ) -> ShareSubmissionResponse:
        response, should_enqueue = runtime_state.submit(payload)
        if should_enqueue:
            background_tasks.add_task(runtime_state.service.run_task, response.taskId)
        return response

    @app.get("/api/share-submissions/{task_id}", response_model=TaskStatusResponse, dependencies=[Depends(verify_auth)])
    def task_status(task_id: str, runtime_state: AppRuntime = Depends(get_runtime)) -> TaskStatusResponse:
        return runtime_state.get_task_status(task_id)

    @app.post("/api/share-submissions/{task_id}/cancel", response_model=CancelTaskResponse, dependencies=[Depends(verify_auth)])
    def cancel_task(task_id: str, runtime_state: AppRuntime = Depends(get_runtime)) -> CancelTaskResponse:
        return runtime_state.cancel_task(task_id)

    static_dir = Path(__file__).resolve().parents[1] / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    if bootstrap_settings.web_ui_enabled:
        app.include_router(create_web_router(runtime))

    return app
