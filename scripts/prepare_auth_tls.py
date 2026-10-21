"""Generate disposable LOCAL-only TLS fixtures. No CA is installed in the user's trust store."""

import os
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / "var" / "auth-test-tls"
folder.mkdir(parents=True, exist_ok=True)
binary = shutil.which("openssl")
if not binary and os.name == "nt":
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/mingw64/bin/openssl.exe"
    binary = str(candidate) if candidate.is_file() else None
if not binary:
    raise SystemExit("Install OpenSSL from the OS/vendor package manager for local TLS tests.")
subprocess.run([
    binary, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
    "-keyout", str(folder / "key.pem"), "-out", str(folder / "cert.pem"),
    "-subj", "/CN=app.subtrack.test",
    "-addext", "subjectAltName=DNS:app.subtrack.test,DNS:api.subtrack.test",
], check=True, capture_output=True)
print("Generated ignored, short-lived TLS fixtures for app/api.subtrack.test only.")
