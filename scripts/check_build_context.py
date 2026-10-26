"""Prove nested private inputs stay outside images, using synthetic canaries only."""

import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    truth = json.loads((ROOT / "backend/data/receipts/ground_truth.json").read_text())
    expected = {"data/receipts/" + name for name in truth["cases"]}
    failures = []
    for part, nested in (("backend", "data"), ("frontend", "src")):
        context = ROOT / part
        marker = "subtrack-canary-" + uuid.uuid4().hex
        created, directories = [], []
        tag = "subtrack-context-proof:" + part
        try:
            for directory, filename in (
                ("private-emails", marker + ".eml"),
                ("private-statements", marker + ".csv"),
                ("build-context-fixture", ".env." + marker),
            ):
                parent = context / nested / directory
                if not parent.exists():
                    parent.mkdir()
                    directories.append(parent)
                path = parent / filename
                path.resolve().relative_to(context.resolve())
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(
                        "Synthetic build-context canary; no credentials or financial data.\n"
                    )
                created.append(path)
            subprocess.run(
                ["docker", "build", "-q", "-t", tag, "-f", "-", str(context)],
                input="FROM python:3.12-slim\nWORKDIR /proof\nCOPY . .\n",
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            program = (
                "import json;from pathlib import Path;root=Path('/proof');"
                f"marker={marker!r};"
                "print(json.dumps({'copied_canaries':sum(marker in p.name for p in root.rglob('*')),"
                "'emails':sorted(str(p.relative_to(root)) for p in root.rglob('*.eml'))}))"
            )
            report = json.loads(
                subprocess.check_output(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network",
                        "none",
                        tag,
                        "python",
                        "-c",
                        program,
                    ],
                    text=True,
                )
            )
            approved = expected if part == "backend" else set()
            ok = report["copied_canaries"] == 0 and set(report["emails"]) == approved
            print(
                f"{part}: copied canaries={report['copied_canaries']}; "
                f"synthetic email fixtures={len(report['emails'])}; {'PASS' if ok else 'FAIL'}",
                flush=True,
            )
            if not ok:
                failures.append(part)
        finally:
            for path in created:
                path.resolve().relative_to(context.resolve())
                path.unlink()
            for directory in reversed(directories):
                directory.rmdir()  # Only empty directories created by this invocation.
            subprocess.run(
                ["docker", "image", "rm", tag],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    if failures:
        raise SystemExit(
            "Private build-context exclusion failed: " + ", ".join(failures)
        )


if __name__ == "__main__":
    check()
