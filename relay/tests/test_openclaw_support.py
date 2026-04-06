from __future__ import annotations

import unittest
from unittest.mock import patch

from app.openclaw_support import _resolve_executable


class OpenClawSupportTests(unittest.TestCase):
    def test_windows_resolution_prefers_cmd_before_ps1(self) -> None:
        with patch("app.openclaw_support.os.name", "nt"):
            with patch("app.openclaw_support.shutil.which") as mock_which:
                mock_which.side_effect = lambda value: {
                    "openclaw": None,
                    "openclaw.cmd": r"C:\Users\Peter\AppData\Roaming\npm\openclaw.cmd",
                    "openclaw.exe": None,
                    "openclaw.bat": None,
                    "openclaw.ps1": r"C:\Users\Peter\AppData\Roaming\npm\openclaw.ps1",
                }.get(value)

                resolved = _resolve_executable("openclaw")

        self.assertEqual(resolved, r"C:\Users\Peter\AppData\Roaming\npm\openclaw.cmd")


if __name__ == "__main__":
    unittest.main()
