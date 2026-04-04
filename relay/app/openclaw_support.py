from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

WINDOWS_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
WINDOWS_CMD = r"C:\Windows\System32\cmd.exe"
VALID_OPENCLAW_TARGET_MODES = {"agent", "session", "to"}
VALID_THINKING_LEVELS = {"", "off", "minimal", "low", "medium", "high", "xhigh"}


@dataclass(frozen=True)
class OpenClawCommandResolution:
    available: bool
    invocation_prefix: list[str]
    display_command: str
    resolved_path: str | None


def resolve_openclaw_command(command: str) -> OpenClawCommandResolution:
    parts = shlex.split(command, posix=os.name != "nt")
    if not parts:
        return OpenClawCommandResolution(
            available=False,
            invocation_prefix=[],
            display_command=command,
            resolved_path=None,
        )

    executable = parts[0]
    trailing_args = parts[1:]
    resolved_path = _resolve_executable(executable)
    if not resolved_path:
        return OpenClawCommandResolution(
            available=False,
            invocation_prefix=[],
            display_command=command,
            resolved_path=None,
        )

    resolved_lower = resolved_path.lower()
    if os.name == "nt" and resolved_lower.endswith(".ps1"):
        invocation_prefix = [WINDOWS_POWERSHELL, "-ExecutionPolicy", "Bypass", "-File", resolved_path, *trailing_args]
    elif os.name == "nt" and (resolved_lower.endswith(".cmd") or resolved_lower.endswith(".bat")):
        invocation_prefix = [WINDOWS_CMD, "/c", resolved_path, *trailing_args]
    else:
        invocation_prefix = [resolved_path, *trailing_args]

    return OpenClawCommandResolution(
        available=True,
        invocation_prefix=invocation_prefix,
        display_command=" ".join(shlex.quote(part) for part in invocation_prefix),
        resolved_path=resolved_path,
    )


def _resolve_executable(executable: str) -> str | None:
    path = Path(executable)
    if path.is_absolute():
        return str(path) if path.exists() else None

    resolved = shutil.which(executable)
    if resolved:
        return resolved

    if os.name == "nt":
        for suffix in (".ps1", ".cmd", ".exe", ".bat"):
            resolved = shutil.which(f"{executable}{suffix}")
            if resolved:
                return resolved
    return None
