import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent
    args = sys.argv[1:] or ["start"]
    command = [sys.executable, "-m", "relay", *args]
    completed = subprocess.run(command, cwd=parent_dir)
    raise SystemExit(completed.returncode)
