"""Run real compiled-asset CSP browser checks; restore the original local API configuration."""

import os
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    original = dict(os.environ)
    port = int(original.get("CSP_WEB_PORT", "5174"))
    if not 1024 <= port <= 65535:
        raise SystemExit("CSP_WEB_PORT must be an unprivileged local port")
    fixed = dict(
        original, E2E_PRODUCTION_CSP="1", E2E_BASE_URL=f"http://localhost:{port}"
    )
    compose = [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.csp-test.yml",
    ]
    browser_name = "subtrack-csp-browser-" + uuid.uuid4().hex[:12]
    image = original.get("CSP_BROWSER_IMAGE")
    try:
        subprocess.run(
            compose + ["up", "--build", "-d", "--wait", "csp-web"],
            cwd=ROOT,
            env=fixed,
            check=True,
            timeout=900,
        )
        command = [
            "node",
            "node_modules/@playwright/test/cli.js",
            "test",
            "csp.spec.ts",
        ]
        # Optional existing Linux browser image for Windows installations. Mount at the same
        # path only for browser code; this profile never invokes Docker from inside the browser.
        if image:
            command = [
                "docker",
                "run",
                "--rm",
                "--pull",
                "never",
                "--name",
                browser_name,
                "--label",
                "subtrack.csp-test=true",
                "--network",
                "host",
                "--ipc",
                "host",
                "--mount",
                f"type=bind,source={ROOT},target=/repo",
                "--workdir",
                "/repo/frontend",
                "--env",
                "E2E_PRODUCTION_CSP=1",
                "--env",
                f"E2E_BASE_URL=http://localhost:{port}",
                image,
            ] + command
            subprocess.run(command, cwd=ROOT, env=fixed, check=True, timeout=900)
        else:
            subprocess.run(
                command, cwd=ROOT / "frontend", env=fixed, check=True, timeout=900
            )
    finally:
        try:
            if image:
                owner = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{index .Config.Labels "subtrack.csp-test"}}',
                        browser_name,
                    ],
                    capture_output=True,
                    timeout=30,
                )
                if owner.returncode == 0:
                    if owner.stdout.strip() != b"true":
                        raise RuntimeError(
                            "Refusing to remove an unowned browser container"
                        )
                    subprocess.run(
                        ["docker", "rm", "-f", browser_name], check=True, timeout=60
                    )
            subprocess.run(
                compose + ["stop", "csp-web"],
                cwd=ROOT,
                env=original,
                check=True,
                timeout=60,
            )
            subprocess.run(
                compose + ["rm", "-f", "csp-web"],
                cwd=ROOT,
                env=original,
                check=True,
                timeout=60,
            )
        finally:
            subprocess.run(
                ["docker", "compose", "up", "-d", "--wait", "api", "worker"],
                cwd=ROOT,
                env=original,
                check=True,
                timeout=180,
            )


if __name__ == "__main__":
    main()
