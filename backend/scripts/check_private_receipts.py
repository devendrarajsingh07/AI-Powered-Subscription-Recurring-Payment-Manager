"""Owner-run terminal-only receipt check. Never uploads, writes files, or contacts a provider."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.email_receipts import MAX_BYTES, ReceiptError, parse_receipt  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Private local redacted .eml files")
    args = parser.parse_args()
    if len(args.files) > 100:
        parser.error("Check at most 100 files per invocation")
    print("Local review only: not proof of payment/authenticity or a measured accuracy score.")
    accepted = 0
    for index, path in enumerate(args.files, start=1):
        try:
            if path.suffix.lower() != ".eml":
                raise ReceiptError("unsupported_receipt", "Choose EML")
            with path.open("rb") as source:
                value = parse_receipt(source.read(MAX_BYTES + 1))["rows"][0]
            output = {
                name: value[name] for name in ("date", "description", "amount", "type", "flags")
            }
            print(json.dumps({"file_index": index, "review_required": True, "fields": output}))
            accepted += 1
        except ReceiptError as error:
            print(json.dumps({"file_index": index, "rejected": error.code}))
        except OSError:
            print(json.dumps({"file_index": index, "rejected": "file_unavailable"}))
    print(json.dumps({"files": len(args.files), "review_candidates": accepted}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
