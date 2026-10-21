"""Free-host synthetic demo only; production uses a separate migration release step."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    if os.environ.get("ENVIRONMENT") != "development":
        raise SystemExit("This entry point is only for a development/demo deployment.")
    if len(os.environ.get("JWT_SECRET", "")) < 32:
        raise SystemExit("Configure a generated JWT_SECRET before starting the demo.")
    try:
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be an integer between 1 and 65535.") from None
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    # This entry point is exclusively the hosted public demo; fail closed on file uploads/login.
    os.environ["PUBLIC_DEMO_ONLY"] = "true"
    os.environ["AUTH_SESSION_MODE"] = "demo"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--workers",
            "1",
            "--no-access-log",
        ],
    )


if __name__ == "__main__":
    main()
