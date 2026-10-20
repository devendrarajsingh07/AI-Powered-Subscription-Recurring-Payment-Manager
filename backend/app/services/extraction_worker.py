"""Private subprocess entry point. JSON stdin/stdout pipes only; never log row text."""

import json
import os
import sys


def main():
    # Set limits before importing parsers or reading untrusted input. All child programs inherit
    # them. This bounds each process, not aggregate cgroup memory or network access.
    import resource

    memory = int(os.environ["EXTRACT_MEMORY_MB"]) * 1024 * 1024
    cpu = int(os.environ["EXTRACT_CPU_SECONDS"])
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    from app.services.statement_extraction import ExtractionError, extract

    def progress(done, total):
        print(
            json.dumps(dict(event="progress", processed_pages=done, total_pages=total)), flush=True
        )

    try:
        import base64

        request = json.loads(sys.stdin.buffer.read(15 * 1024 * 1024))
        data = base64.b64decode(request.pop("data"), validate=True)
        result = extract(
            data,
            request["filename"],
            request.pop("password", ""),
            os.getcwd(),
            request["limits"],
            progress,
        )
        print(json.dumps(dict(event="result", result=result)), flush=True)
    except ExtractionError as exc:
        print(json.dumps(dict(event="error", code=exc.code, message=str(exc))), flush=True)
    except Exception:
        # Parser exceptions can include passwords, file text or binary fragments.
        print(
            json.dumps(
                dict(
                    event="error",
                    code="invalid_statement",
                    message="Statement could not be read safely. Re-export it or use CSV.",
                )
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
