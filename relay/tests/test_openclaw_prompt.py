from __future__ import annotations

import unittest
from pathlib import Path

from app.config import Settings
from app.executors.openclaw_prompt import build_openclaw_message
from app.models import TaskRecord


def make_settings() -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8080,
        auth_token="",
        service_name="Relay Prompt Test",
        service_version="0.1.0",
        default_mode="paper_harvest_v1",
        executor_kind="openclaw",
        shell_command_template="",
        shell_command_timeout_seconds=30,
        openclaw_command="openclaw",
        openclaw_target_mode="agent",
        openclaw_local=True,
        openclaw_agent_id="main",
        openclaw_session_id="",
        openclaw_to="",
        openclaw_channel="",
        openclaw_thinking="",
        openclaw_json_output=False,
        openclaw_browser_profile="openclaw",
        openclaw_wechat_use_browser=True,
        openclaw_timeout_seconds=60,
        openclaw_session_lock_retry_attempts=2,
        openclaw_session_lock_retry_base_seconds=1,
        openclaw_session_lock_defer_cycles=1,
        openclaw_session_lock_defer_seconds=1,
        openclaw_network_retry_attempts=2,
        openclaw_network_retry_base_seconds=1,
        max_concurrent_tasks=2,
        startup_recovery_limit=25,
        startup_recovery_stagger_ms=0,
        task_retention_days=30,
        task_result_char_limit=1200,
        task_error_char_limit=1200,
        task_file_char_limit=8000,
        task_cleanup_interval_seconds=43200,
        task_request_preview_char_limit=2000,
        task_keep_success_debug_files=False,
        workspace_dir=Path("."),
        data_dir=Path("."),
        tasks_dir=Path("."),
        logs_dir=Path("."),
        database_path=Path("relay.sqlite3"),
        web_ui_enabled=True,
        web_ui_local_only=True,
        runtime_config_path=Path("config.json"),
    )


def make_task(mode: str) -> TaskRecord:
    return TaskRecord(
        task_id="task-1",
        client_submission_id="client-1",
        mode=mode,
        source="wechat_article",
        raw_text="https://example.com/article",
        raw_url="https://example.com/article",
        normalized_url="https://example.com/article",
        client_app_version="1.0",
        status="queued",
        stage_label="Queued",
        result_summary="",
        error_message="",
        error_code="",
        relay_message="Accepted",
        executor_kind="openclaw",
        task_dir=".",
        status_meta={},
        timeline=[],
        created_at="2026-04-04T00:00:00+00:00",
        updated_at="2026-04-04T00:00:00+00:00",
        started_at=None,
        completed_at=None,
    )


class OpenClawPromptTests(unittest.TestCase):
    def test_strict_prompt_requests_topic_count_and_takeaway(self) -> None:
        message = build_openclaw_message(make_settings(), make_task("paper_harvest_v1"), article_body="Body")
        self.assertIn("ARTICLE_TOPIC:", message)
        self.assertIn("EXPLICIT_PAPER_COUNT:", message)
        self.assertIn("KEY_TAKEAWAY:", message)
        self.assertNotIn("POSSIBLY_RELATED_PAPERS:", message)

    def test_relaxed_prompt_requests_possible_related_papers(self) -> None:
        message = build_openclaw_message(make_settings(), make_task("paper_harvest_relaxed_v1"), article_body="Body")
        self.assertIn("ARTICLE_TOPIC:", message)
        self.assertIn("EXPLICIT_PAPER_COUNT:", message)
        self.assertIn("POSSIBLY_RELATED_PAPERS:", message)
        self.assertIn("KEY_TAKEAWAY:", message)


if __name__ == "__main__":
    unittest.main()
