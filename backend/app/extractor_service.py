"""Credential-free Unix-socket parser service. Run with network_mode:none and cgroup limits."""

import base64
import fcntl
import json
import logging
import os
import socket
import socketserver
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from queue import Empty, Full, Queue
from threading import BoundedSemaphore, Event, Thread
from types import SimpleNamespace

from app.services.extraction_runner import run_extraction
from app.services.statement_extraction import ExtractionError

MAX_REQUEST = 15 * 1024 * 1024
CAPACITY = BoundedSemaphore(1)
LIMITS = SimpleNamespace(
    statement_max_mb=10,
    statement_max_pages=30,
    statement_max_megapixels=25,
    statement_page_seconds=20,
    statement_memory_mb=512,
    statement_timeout_seconds=120,
)


def assert_no_credentials():
    if any(
        name in os.environ
        for name in (
            "DATABASE_URL",
            "JWT_SECRET",
            "LLM_API_KEY",
            "SMTP_PASSWORD",
            "POSTGRES_PASSWORD",
        )
    ):
        raise RuntimeError("Extractor must not receive application or database credentials")


class Handler(BaseHTTPRequestHandler):
    server_version = "SubTrackExtractor"

    def log_message(self, *args):
        pass  # No request bodies, descriptions, amounts, passwords or headers in logs.

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path not in ("/extract", "/preflight") or self.headers.get("Transfer-Encoding"):
            self.send_error(400, "Unsupported bounded request")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= MAX_REQUEST:
                raise ValueError
        except ValueError:
            self.send_error(413, "Input exceeds the request limit")
            return
        if not CAPACITY.acquire(blocking=False):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        stop, queue = Event(), Queue(maxsize=16)
        worker = None
        try:
            self.connection.settimeout(5)
            raw = self.rfile.read(size)
            request = json.loads(raw)
            if set(request) != {"data", "filename", "password"}:
                raise ValueError
            data = base64.b64decode(request["data"], validate=True)
            filename, password = request["filename"], request["password"]
            if (
                len(data) > 10 * 1024 * 1024
                or not isinstance(filename, str)
                or len(filename) > 255
                or not isinstance(password, str)
                or len(password) > 256
            ):
                raise ValueError
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def publish(value):
                while not stop.is_set():
                    try:
                        queue.put(value, timeout=0.1)
                        return
                    except Full:
                        pass

            def run():
                try:
                    result = run_extraction(
                        data,
                        filename,
                        password,
                        config=LIMITS,
                        operation="preflight" if self.path == "/preflight" else "extract",
                        cancelled=stop.is_set,
                        progress=lambda done, total: publish(
                            {
                                "event": "progress",
                                "processed_pages": done,
                                "total_pages": total,
                            }
                        ),
                    )
                    publish({"event": "result", "result": result})
                except ExtractionError as exc:
                    publish({"event": "error", "code": exc.code, "message": str(exc)[:255]})
                except Exception:
                    publish(
                        {
                            "event": "error",
                            "code": "extraction_failed",
                            "message": "Statement could not be read safely; export CSV.",
                        }
                    )

            worker = Thread(target=run, daemon=True)
            worker.start()
            while True:
                try:
                    event = queue.get(timeout=0.5)
                except Empty:
                    event = {"event": "heartbeat"}
                self.wfile.write(json.dumps(event, separators=(",", ":")).encode() + b"\n")
                self.wfile.flush()
                if event["event"] in ("result", "error"):
                    break
        except (ValueError, TypeError, KeyError):
            self.send_error(422, "Invalid bounded extraction input")
        except (OSError, TimeoutError):
            pass  # Disconnected worker/API cancels the private subprocess group below.
        finally:
            stop.set()
            if worker:
                worker.join(timeout=5)
                if worker.is_alive():
                    os._exit(1)  # Fail closed; container restart removes its tmpfs/processes.
            CAPACITY.release()


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    request_queue_size = 4


def main():
    assert_no_credentials()
    logging.disable(logging.CRITICAL)
    path = Path(os.environ.get("EXTRACTOR_SOCKET", "/var/subtrack/extractor/rpc.sock"))
    if "--health" in sys.argv[1:]:
        try:
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(3)
                connection.connect(str(path))
                connection.sendall(b"GET /health HTTP/1.0" + bytes((13, 10, 13, 10)))
                healthy = b" 200 " in connection.recv(128)
        except OSError:
            healthy = False
        raise SystemExit(0 if healthy else 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    # One effective parser owns the socket, including during a container restart.
    with (path.parent / "service.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if path.is_socket():
            path.unlink()
        with Server(str(path), Handler) as server:
            path.chmod(0o660)
            server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
