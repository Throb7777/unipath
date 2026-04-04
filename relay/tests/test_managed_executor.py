from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.executors.base import ExecutorHealth
from app.executors.common import ManagedTaskExecutor


class DummyExecutor(ManagedTaskExecutor):
    executor_id = "dummy"
    display_name = "Dummy Executor"

    def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            executorId=self.executor_id,
            label=self.display_name,
            available=True,
            message="dummy ok",
        )

    async def execute(self, task_id: str) -> None:  # pragma: no cover - not needed here
        raise NotImplementedError


class ManagedExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_cancellable_process_handles_large_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_dir = Path(tempdir)
            executor = DummyExecutor(
                settings=SimpleNamespace(workspace_dir=workspace_dir),
                store=SimpleNamespace(get=lambda _task_id: None),
            )

            large_output = "x" * 12000
            command = [
                sys.executable,
                "-c",
                f"import sys; sys.stdout.write({large_output!r})",
            ]

            result = await executor._run_cancellable_process(
                command,
                task_id=None,
                timeout_seconds=5,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, large_output)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
