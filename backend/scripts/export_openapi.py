"""Export/check the runtime API contract and a readable endpoint inventory."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


def artifacts():
    schema = app.openapi()
    specification = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    lines = [
        "# SubTrack API contract",
        "",
        "Generated from `/api/v1/openapi.json`. Do not edit manually.",
        "",
        "Money is serialized as decimal strings. Dates use ISO-8601. Every business route",
        "requires the HTTP Bearer access token. Health and register/login are public.",
        "",
        "| Method | Route | Auth | Purpose |",
        "| --- | --- | --- | --- |",
    ]
    for path, methods in sorted(schema["paths"].items()):
        for method, operation in sorted(methods.items()):
            if method not in ("get", "post", "patch", "put", "delete"):
                continue
            lines.append(
                f"| {method.upper()} | `{path}` | "
                f"{'JWT' if operation.get('security') else 'Public'} | {operation['summary']} |"
            )
    lines += [
        "",
        "See the JSON contract for request/response schemas, examples, filters, bounds,",
        "pagination and error envelopes. Upload mappings are JSON encoded multipart form fields.",
        "The asynchronous upload response is 202; poll its `id` until `done` or `failed`.",
        "",
    ]
    return specification, "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / "openapi"
    specification, summary = artifacts()
    if args.check:
        for filename, expected in (("openapi.json", specification), ("SUMMARY.md", summary)):
            if (directory / filename).read_text(encoding="utf-8") != expected:
                raise SystemExit(f"OpenAPI artifact stale: {filename}; regenerate the contract")
        print("OpenAPI contract and summary are current")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "openapi.json").write_text(specification, encoding="utf-8")
        (directory / "SUMMARY.md").write_text(summary, encoding="utf-8")
        print("Exported OpenAPI JSON and endpoint summary")


if __name__ == "__main__":
    main()
