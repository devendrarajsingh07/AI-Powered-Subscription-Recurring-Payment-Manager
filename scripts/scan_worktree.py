"""Scan versioned and non-ignored source, never dependency caches or private .env files."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
).decode().split("\0")
(root / "var").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="subtrack-secret-scan-", dir=root / "var") as directory:
    target = Path(directory)
    for name in files:
        source = root / name
        if name and source.is_file():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    result = subprocess.run([sys.argv[1], "dir", str(target), "--redact"], check=False)
    raise SystemExit(result.returncode)
