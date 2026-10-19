"""Freeze the existing server clock for real-stack tests; restore it even on failure."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    original = os.environ.copy()
    fixed = dict(original, APP_TEST_AS_OF=json.loads(
        (ROOT / 'backend/data/ground_truth.json').read_text())['as_of'])
    command = ['docker', 'compose', 'up', '-d', '--wait', 'api']
    try:
        subprocess.run(command, cwd=ROOT, env=fixed, check=True)
        result = subprocess.run(['node', 'node_modules/@playwright/test/cli.js', 'test'],
                                cwd=ROOT/'frontend', env=fixed)
        return result.returncode
    finally:
        subprocess.run(command, cwd=ROOT, env=original, check=True)


if __name__ == '__main__':
    raise SystemExit(main())
