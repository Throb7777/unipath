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


if __name__ == "__main__":
    unittest.main()
