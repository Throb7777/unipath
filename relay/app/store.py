from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from app.models import ShareSubmissionRequest, TaskRecord, utc_now_iso

RECOVERABLE_STATUSES = ("queued", "preparing", "running", "finalizing", "cancelling")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")
logger = logging.getLogger("relay.store")


class TaskStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            logger.warning("sqlite_wal_unavailable database=%s; falling back to DELETE journal mode", self.database_path)
            connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    client_submission_id TEXT NOT NULL UNIQUE,
                    mode TEXT NOT NULL,
                    source TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    raw_url TEXT,
                    normalized_url TEXT NOT NULL,
                    client_app_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage_label TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    relay_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )
            self._ensure_column(connection, "error_code", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "executor_kind", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "task_dir", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "status_meta", "TEXT NOT NULL DEFAULT '{}' ")
            self._ensure_column(connection, "timeline_json", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at ON tasks (status, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_completed_at ON tasks (status, completed_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_executor_created_at ON tasks (executor_kind, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_source_created_at ON tasks (source, created_at DESC)")
            connection.commit()

    def _ensure_column(self, connection: sqlite3.Connection, column_name: str, definition: str) -> None:
        rows = connection.execute("PRAGMA table_info(tasks)").fetchall()
        existing = {row[1] for row in rows}
        if column_name not in existing:
            connection.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {definition}")

    def create_or_get(
        self,
        payload: ShareSubmissionRequest,
        *,
        executor_kind: str,
        tasks_root: Path,
    ) -> tuple[TaskRecord, bool]:
        with self._lock:
            existing = self.get_by_client_submission_id(payload.clientSubmissionId)
            if existing is not None:
                return existing, False

            now = utc_now_iso()
            task_id = f"relay-{uuid.uuid4().hex[:12]}"
            task_dir = str((tasks_root / task_id).resolve())
            record = TaskRecord(
                task_id=task_id,
                client_submission_id=payload.clientSubmissionId,
                mode=payload.mode,
                source=payload.source,
                raw_text=payload.rawText,
                raw_url=payload.rawUrl,
                normalized_url=payload.normalizedUrl,
                client_app_version=payload.clientAppVersion,
                status="queued",
                stage_label="Queued for execution",
                result_summary="",
                error_message="",
                error_code="",
                relay_message="Accepted for relay processing.",
                executor_kind=executor_kind,
                task_dir=task_dir,
                status_meta={"executorKind": executor_kind},
                timeline=[
                    {
                        "stepId": "queued",
                        "label": "Queued for execution",
                        "status": "queued",
                        "at": now,
                        "message": "Accepted for relay processing.",
                    },
                ],
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
            )
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO tasks (
                        task_id, client_submission_id, mode, source, raw_text, raw_url,
                        normalized_url, client_app_version, status, stage_label,
                        result_summary, error_message, error_code, relay_message,
                        executor_kind, task_dir, status_meta, timeline_json,
                        created_at, updated_at, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.task_id,
                        record.client_submission_id,
                        record.mode,
                        record.source,
                        record.raw_text,
                        record.raw_url,
                        record.normalized_url,
                        record.client_app_version,
                        record.status,
                        record.stage_label,
                        record.result_summary,
                        record.error_message,
                        record.error_code,
                        record.relay_message,
                        record.executor_kind,
                        record.task_dir,
                        self._dump_json(record.status_meta),
                        self._dump_list_json(record.timeline),
                        record.created_at,
                        record.updated_at,
                        record.started_at,
                        record.completed_at,
                    ),
                )
                connection.commit()
            return record, True

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_record(row)

    def get_by_client_submission_id(self, client_submission_id: str) -> Optional[TaskRecord]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE client_submission_id = ?",
                (client_submission_id,),
            ).fetchone()
        return self._row_to_record(row)

    def list_recoverable(self, limit: int = 200) -> list[TaskRecord]:
        placeholders = ",".join("?" for _ in RECOVERABLE_STATUSES)
        query = f"SELECT * FROM tasks WHERE status IN ({placeholders}) ORDER BY created_at ASC LIMIT ?"
        with self._connection() as connection:
            rows = connection.execute(query, (*RECOVERABLE_STATUSES, limit)).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def list_terminal_before(self, threshold_iso: str, limit: int = 500) -> list[TaskRecord]:
        placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
        query = (
            f"SELECT * FROM tasks WHERE status IN ({placeholders}) AND completed_at IS NOT NULL "
            "AND completed_at < ? ORDER BY completed_at ASC LIMIT ?"
        )
        with self._connection() as connection:
            rows = connection.execute(query, (*TERMINAL_STATUSES, threshold_iso, limit)).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def list_tasks(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        executor_kind: str | None = None,
        source: str | None = None,
    ) -> list[TaskRecord]:
        clauses: list[str] = []
        args: list[Any] = []
        if status:
            clauses.append("status = ?")
            args.append(status)
        if executor_kind:
            clauses.append("executor_kind = ?")
            args.append(executor_kind)
        if source:
            clauses.append("source = ?")
            args.append(source)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM tasks {where_clause} ORDER BY created_at DESC LIMIT ?"
        with self._connection() as connection:
            rows = connection.execute(query, (*args, limit)).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def list_task_summaries(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        executor_kind: str | None = None,
        source: str | None = None,
    ) -> list[TaskRecord]:
        clauses: list[str] = []
        args: list[Any] = []
        if status:
            clauses.append("status = ?")
            args.append(status)
        if executor_kind:
            clauses.append("executor_kind = ?")
            args.append(executor_kind)
        if source:
            clauses.append("source = ?")
            args.append(source)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = (
            "SELECT task_id, client_submission_id, mode, source, normalized_url, client_app_version, "
            "status, stage_label, result_summary, error_message, error_code, relay_message, "
            "executor_kind, status_meta, created_at, updated_at, started_at, completed_at "
            f"FROM tasks {where_clause} ORDER BY created_at DESC LIMIT ?"
        )
        with self._connection() as connection:
            rows = connection.execute(query, (*args, limit)).fetchall()
        return [record for row in rows if (record := self._row_to_summary_record(row)) is not None]

    def delete_tasks(self, task_ids: list[str]) -> int:
        if not task_ids:
            return 0
        placeholders = ",".join("?" for _ in task_ids)
        with self._connection() as connection:
            cursor = connection.execute(f"DELETE FROM tasks WHERE task_id IN ({placeholders})", task_ids)
            connection.commit()
            return cursor.rowcount

    def request_cancel(self, task_id: str, *, relay_message: str) -> Optional[TaskRecord]:
        with self._lock:
            current = self.get(task_id)
            if current is None:
                return None
            if current.status in TERMINAL_STATUSES:
                return current

            immediate_cancel = current.status == "queued"
            next_status = "cancelled" if immediate_cancel else "cancelling"
            next_stage = "Cancelled" if immediate_cancel else "Cancellation requested"
            completed_at = utc_now_iso() if immediate_cancel else None
            updated = self._write_updated_record(
                current=current,
                status=next_status,
                stage_label=next_stage,
                relay_message=relay_message,
                error_message="",
                error_code="",
                completed_at=completed_at,
                status_meta={**current.status_meta, "cancelRequested": True},
            )
            return updated

    def update_status(
        self,
        task_id: str,
        *,
        status: str,
        stage_label: str,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        relay_message: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        status_meta: Optional[dict[str, Any]] = None,
    ) -> Optional[TaskRecord]:
        with self._lock:
            current = self.get(task_id)
            if current is None:
                return None

            return self._write_updated_record(
                current=current,
                status=status,
                stage_label=stage_label,
                result_summary=result_summary,
                error_message=error_message,
                error_code=error_code,
                relay_message=relay_message,
                started_at=started_at,
                completed_at=completed_at,
                status_meta=status_meta,
            )

    def _dump_json(self, value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _dump_list_json(self, value: list[dict[str, Any]]) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json(self, raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _load_list_json(self, raw: str | None) -> list[dict[str, Any]]:
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _build_timeline(
        self,
        current: TaskRecord,
        *,
        status: str,
        stage_label: str,
        relay_message: str,
        updated_at: str,
    ) -> list[dict[str, Any]]:
        timeline = list(current.timeline)
        entry = {
            "stepId": status,
            "label": stage_label,
            "status": status,
            "at": updated_at,
            "message": relay_message,
        }
        last_entry = timeline[-1] if timeline else None
        if last_entry != entry:
            timeline.append(entry)
        return timeline

    def _write_updated_record(
        self,
        *,
        current: TaskRecord,
        status: str,
        stage_label: str,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        relay_message: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        status_meta: Optional[dict[str, Any]] = None,
    ) -> TaskRecord:
        next_result_summary = current.result_summary if result_summary is None else result_summary
        next_error_message = current.error_message if error_message is None else error_message
        next_error_code = current.error_code if error_code is None else error_code
        next_relay_message = current.relay_message if relay_message is None else relay_message
        next_started_at = current.started_at if started_at is None else started_at
        next_completed_at = current.completed_at if completed_at is None else completed_at
        next_status_meta = current.status_meta if status_meta is None else status_meta
        if (
            current.status == status
            and current.stage_label == stage_label
            and current.result_summary == next_result_summary
            and current.error_message == next_error_message
            and current.error_code == next_error_code
            and current.relay_message == next_relay_message
            and current.started_at == next_started_at
            and current.completed_at == next_completed_at
            and current.status_meta == next_status_meta
        ):
            return current
        updated_at = utc_now_iso()
        next_timeline = self._build_timeline(
            current,
            status=status,
            stage_label=stage_label,
            relay_message=next_relay_message,
            updated_at=updated_at,
        )

        with self._connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?,
                    stage_label = ?,
                    result_summary = ?,
                    error_message = ?,
                    error_code = ?,
                    relay_message = ?,
                    updated_at = ?,
                    started_at = ?,
                    completed_at = ?,
                    status_meta = ?,
                    timeline_json = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    stage_label,
                    next_result_summary,
                    next_error_message,
                    next_error_code,
                    next_relay_message,
                    updated_at,
                    next_started_at,
                    next_completed_at,
                    self._dump_json(next_status_meta),
                    self._dump_list_json(next_timeline),
                    current.task_id,
                ),
            )
            connection.commit()
        return replace(
            current,
            status=status,
            stage_label=stage_label,
            result_summary=next_result_summary,
            error_message=next_error_message,
            error_code=next_error_code,
            relay_message=next_relay_message,
            status_meta=next_status_meta,
            timeline=next_timeline,
            updated_at=updated_at,
            started_at=next_started_at,
            completed_at=next_completed_at,
        )

    def _row_to_record(self, row: sqlite3.Row | None) -> Optional[TaskRecord]:
        if row is None:
            return None
        return TaskRecord(
            task_id=row["task_id"],
            client_submission_id=row["client_submission_id"],
            mode=row["mode"],
            source=row["source"],
            raw_text=row["raw_text"],
            raw_url=row["raw_url"],
            normalized_url=row["normalized_url"],
            client_app_version=row["client_app_version"],
            status=row["status"],
            stage_label=row["stage_label"],
            result_summary=row["result_summary"],
            error_message=row["error_message"],
            error_code=row["error_code"] if "error_code" in row.keys() else "",
            relay_message=row["relay_message"],
            executor_kind=row["executor_kind"] if "executor_kind" in row.keys() else "",
            task_dir=row["task_dir"] if "task_dir" in row.keys() else "",
            status_meta=self._load_json(row["status_meta"] if "status_meta" in row.keys() else None),
            timeline=self._load_list_json(row["timeline_json"] if "timeline_json" in row.keys() else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def _row_to_summary_record(self, row: sqlite3.Row | None) -> Optional[TaskRecord]:
        if row is None:
            return None
        return TaskRecord(
            task_id=row["task_id"],
            client_submission_id=row["client_submission_id"],
            mode=row["mode"],
            source=row["source"],
            raw_text="",
            raw_url=None,
            normalized_url=row["normalized_url"],
            client_app_version=row["client_app_version"],
            status=row["status"],
            stage_label=row["stage_label"],
            result_summary=row["result_summary"],
            error_message=row["error_message"],
            error_code=row["error_code"] if "error_code" in row.keys() else "",
            relay_message=row["relay_message"],
            executor_kind=row["executor_kind"] if "executor_kind" in row.keys() else "",
            task_dir="",
            status_meta=self._load_json(row["status_meta"] if "status_meta" in row.keys() else None),
            timeline=[],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
