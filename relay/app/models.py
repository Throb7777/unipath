from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field
from app.user_facing import build_diagnostic_summary, problem_title_for_task, result_summary_for_output, suggested_actions_for_task


class ShareSubmissionRequest(BaseModel):
    mode: str = Field(min_length=1)
    source: str = Field(min_length=1)
    rawText: str = ""
    rawUrl: Optional[str] = None
    normalizedUrl: str = Field(min_length=1)
    clientSubmissionId: str = Field(min_length=1)
    clientAppVersion: str = ""


class ShareSubmissionResponse(BaseModel):
    taskId: str
    message: str


class ClientConfigResponse(BaseModel):
    serviceName: str
    serviceVersion: str
    defaultMode: str
    modes: list[dict]


class TaskTimelineEntry(BaseModel):
    stepId: str
    label: str
    status: str
    at: str
    message: str = ""


class TaskStatusResponse(BaseModel):
    taskId: str
    status: str
    stageLabel: str
    mode: str
    source: str
    normalizedUrl: str
    resultSummary: str = ""
    errorMessage: str = ""
    errorCode: str = ""
    relayMessage: str = ""
    executorKind: str = ""
    taskDir: str = ""
    statusMeta: dict[str, Any] = Field(default_factory=dict)
    problemTitle: str = ""
    suggestedActions: list[str] = Field(default_factory=list)
    diagnosticSummary: str = ""
    durationMs: Optional[int] = None
    canCancel: bool = False
    timeline: list[TaskTimelineEntry] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None


class CancelTaskResponse(BaseModel):
    taskId: str
    status: str
    message: str
    canCancel: bool = False


@dataclass(frozen=True)
class TimelineEvent:
    step_id: str
    label: str
    status: str
    at: str
    message: str = ""


@dataclass(frozen=True)
class TaskExecutionContext:
    task_id: str
    executor_kind: str
    task_dir: str
    workspace_dir: str
    cancel_requested: bool = False
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskExecutionResult:
    status: str
    stage_label: str
    result_summary: str = ""
    error_message: str = ""
    error_code: str = ""
    relay_message: str = ""
    status_meta: dict[str, Any] = field(default_factory=dict)
    timeline_events: list[TimelineEvent] = field(default_factory=list)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    client_submission_id: str
    mode: str
    source: str
    raw_text: str
    raw_url: Optional[str]
    normalized_url: str
    client_app_version: str
    status: str
    stage_label: str
    result_summary: str
    error_message: str
    error_code: str
    relay_message: str
    executor_kind: str
    task_dir: str
    status_meta: dict[str, Any]
    timeline: list[dict[str, Any]]
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]

    def to_status_response(self) -> TaskStatusResponse:
        payload = asdict(self)
        duration_ms = _compute_duration_ms(
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            completed_at=payload["completed_at"],
        )
        display_summary = result_summary_for_output(
            mode=payload["mode"],
            executor_kind=payload["executor_kind"],
            raw_summary=payload["result_summary"],
            normalized_url=payload["normalized_url"],
            fallback_message=payload["relay_message"],
        )
        problem_title = problem_title_for_task(
            status=payload["status"],
            error_code=payload["error_code"],
        )
        suggested_actions = suggested_actions_for_task(
            status=payload["status"],
            error_code=payload["error_code"],
        )
        diagnostic_summary = build_diagnostic_summary(
            task_id=payload["task_id"],
            status=payload["status"],
            stage_label=payload["stage_label"],
            mode=payload["mode"],
            source=payload["source"],
            executor_kind=payload["executor_kind"],
            error_code=payload["error_code"],
            relay_message=payload["relay_message"],
            error_message=payload["error_message"],
            normalized_url=payload["normalized_url"],
            duration_ms=duration_ms,
            timeline=payload["timeline"],
        )
        return TaskStatusResponse(
            taskId=payload["task_id"],
            status=payload["status"],
            stageLabel=payload["stage_label"],
            mode=payload["mode"],
            source=payload["source"],
            normalizedUrl=payload["normalized_url"],
            resultSummary=display_summary,
            errorMessage=payload["error_message"],
            errorCode=payload["error_code"],
            relayMessage=payload["relay_message"],
            executorKind=payload["executor_kind"],
            taskDir=payload["task_dir"],
            statusMeta=payload["status_meta"],
            problemTitle=problem_title,
            suggestedActions=suggested_actions,
            diagnosticSummary=diagnostic_summary,
            durationMs=duration_ms,
            canCancel=payload["status"] in {"queued", "preparing", "running", "finalizing"},
            timeline=[TaskTimelineEntry(**entry) for entry in payload["timeline"]],
            createdAt=payload["created_at"],
            updatedAt=payload["updated_at"],
            startedAt=payload["started_at"],
            completedAt=payload["completed_at"],
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _compute_duration_ms(*, created_at: str, updated_at: str, completed_at: Optional[str]) -> Optional[int]:
    try:
        started = datetime.fromisoformat(created_at)
        ended = datetime.fromisoformat(completed_at or updated_at)
    except ValueError:
        return None
    return max(0, int((ended - started).total_seconds() * 1000))
