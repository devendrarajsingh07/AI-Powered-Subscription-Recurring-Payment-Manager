"""Bounded subprocess group, memory-only password pipe, parent-owned private temp cleanup."""

import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread

from app.services.statement_extraction import ExtractionError


def purge_abandoned_temps(root=None):
    """Single-instance startup only: remove our private leftovers after an ungraceful stop."""
    root = Path(root or tempfile.gettempdir()).resolve()
    for candidate in root.glob("subtrack-extract-*"):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        target = candidate.resolve()
        if target.parent != root or not target.name.startswith("subtrack-extract-"):
            raise RuntimeError("Unsafe private temporary cleanup target")
        shutil.rmtree(target)


def run_extraction(
    data,
    filename,
    password,
    *,
    config,
    progress=lambda *args: None,
    cancelled=lambda: False,
    operation="extract",
):
    if operation not in ("extract", "preflight"):
        raise ValueError("Unsupported extraction operation")
    output_limit = (15 if operation == "preflight" else 8) * 1024 * 1024
    if os.name != "posix":
        raise ExtractionError(
            "unsupported_runtime",
            "PDF/OCR requires the Linux Docker API; native Windows extraction is unsupported.",
        )
    if len(data) > config.statement_max_mb * 1024 * 1024:
        raise ExtractionError("file_too_large", "Statement exceeds the configured 10 MB limit.")
    limits = dict(
        pages=config.statement_max_pages,
        megapixels=config.statement_max_megapixels,
        page_seconds=config.statement_page_seconds,
    )
    request = json.dumps(
        dict(
            operation=operation,
            data=base64.b64encode(data).decode("ascii"),
            filename=filename,
            password=password,
            limits=limits,
        )
    ).encode()
    with tempfile.TemporaryDirectory(prefix="subtrack-extract-") as directory:
        env = dict(
            PATH=os.defpath,
            LANG="C.UTF-8",
            HOME=directory,
            TMPDIR=directory,
            PYTHONPATH=str(Path(__file__).resolve().parents[2]),
            PYTHONDONTWRITEBYTECODE="1",
            OMP_THREAD_LIMIT="1",
            EXTRACT_MEMORY_MB=str(config.statement_memory_mb),
            EXTRACT_CPU_SECONDS=str(config.statement_timeout_seconds),
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "app.services.extraction_worker"],
            cwd=directory,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        started, result, error = time.monotonic(), None, None
        messages = Queue(maxsize=64)
        stopped = Event()

        def enqueue(value):
            while not stopped.is_set():
                try:
                    messages.put(value, timeout=0.2)
                    return
                except Full:
                    pass

        def write_input():
            try:
                process.stdin.write(request)
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        def read_output():
            size = 0
            try:
                while not stopped.is_set():
                    line = process.stdout.readline(output_limit + 1)
                    if not line:
                        break
                    size += len(line)
                    if size > output_limit:
                        enqueue(
                            {
                                "event": "error",
                                "code": "extraction_too_large",
                                "message": "Extracted table is too large; split the statement.",
                            }
                        )
                        break
                    try:
                        enqueue(json.loads(line))
                    except ValueError:
                        enqueue(
                            {
                                "event": "error",
                                "code": "invalid_worker_output",
                                "message": "Statement could not be read safely; export CSV.",
                            }
                        )
                        break
            finally:
                enqueue(None)

        writer = Thread(target=write_input, daemon=True)
        reader = Thread(target=read_output, daemon=True)
        writer.start()
        reader.start()
        try:
            while True:
                if cancelled():
                    raise ExtractionError(
                        "cancelled", "Preview cancelled; temporary files were removed."
                    )
                if time.monotonic() - started > config.statement_timeout_seconds:
                    raise ExtractionError(
                        "extraction_timeout",
                        "Extraction exceeded its time limit. Split the file or export CSV.",
                    )
                try:
                    item = messages.get(timeout=0.2)
                except Empty:
                    continue
                if item is None:
                    break
                if item["event"] == "progress":
                    progress(item["processed_pages"], item["total_pages"])
                elif item["event"] == "result":
                    result = item["result"]
                elif item["event"] == "error":
                    error = ExtractionError(item["code"], item["message"])
                    break
            process.wait(timeout=2)
            if error:
                raise error
            if process.returncode or result is None:
                raise ExtractionError(
                    "resource_limit",
                    "Extraction stopped within its resource limits; split the file or export CSV.",
                )
            return result
        finally:
            stopped.set()
            # Also kill lingering OCR/render grandchildren after the leader exits.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            writer.join(timeout=2)
            reader.join(timeout=2)
            process.stdout.close()
