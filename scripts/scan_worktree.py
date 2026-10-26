"""Scan versioned and non-ignored source, never dependency caches or private .env files."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = (
    subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
    )
    .decode()
    .split("\0")
)
# Only reviewed synthetic receipt messages may be versioned. Real EML and dev outbox copies
# stay ignored; `git add -f` must not bypass this privacy gate in CI.
receipt_truth = root / "backend/data/receipts/ground_truth.json"
allowed_eml = (
    {
        "backend/data/receipts/" + name
        for name in json.loads(receipt_truth.read_text(encoding="utf-8"))["cases"]
    }
    if receipt_truth.exists()
    else set()
)
if any(name.lower().endswith(".eml") and name not in allowed_eml for name in files):
    raise SystemExit(
        "Unapproved email source file: only labelled synthetic receipt fixtures may be tracked"
    )
(root / "var").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(
    prefix="subtrack-secret-scan-", dir=root / "var"
) as directory:
    target = Path(directory)
    for name in files:
        source = root / name
        if name and source.is_file():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    result = subprocess.run([sys.argv[1], "dir", str(target), "--redact"], check=False)
    raise SystemExit(result.returncode)
