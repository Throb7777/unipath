from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from app.executors.openclaw import OpenClawExecutor


class OpenClawExecutorTests(unittest.TestCase):
    def test_extract_browser_target_id(self) -> None:
        executor = OpenClawExecutor(
            settings=SimpleNamespace(),
            store=SimpleNamespace(),
        )
        target_id = executor._extract_browser_target_id(
            "opened: https://example.com/article\nid: 6BF82A41FF6B4DE71CE7F820634E2788\n"
        )
        self.assertEqual(target_id, "6BF82A41FF6B4DE71CE7F820634E2788")

    def test_classify_process_failure_surfaces_local_openclaw_state_issue(self) -> None:
        executor = OpenClawExecutor(
            settings=SimpleNamespace(),
            store=SimpleNamespace(),
        )
        stderr = (
            "gateway connect failed: Error: EPERM: operation not permitted, open "
            "'C:\\Users\\Peter\\.openclaw\\identity\\device-auth.json'\n"
            "Error: EPERM: operation not permitted, open "
            "'C:\\Users\\Peter\\.openclaw\\agents\\main\\sessions\\sessions.json.lock'\n"
        )
        error_code, relay_message = executor._classify_process_failure("", stderr)
        self.assertEqual(error_code, "executor_auth_error")
        self.assertIn("local auth or session files", relay_message)


if __name__ == "__main__":
    unittest.main()
