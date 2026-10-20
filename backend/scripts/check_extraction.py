"""Private local check: terminal JSON only, no database/LLM/network or repository writes."""

import argparse
import getpass
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.extraction_runner import run_extraction  # noqa: E402
from app.services.statement_extraction import ExtractionError  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("statement", type=Path)
    parser.add_argument(
        "--password",
        action="store_true",
        help="Prompt privately; never pass the password as an argument",
    )
    args = parser.parse_args()
    cfg = get_settings()
    try:
        with args.statement.open("rb") as handle:
            data = handle.read(cfg.statement_max_mb * 1024 * 1024 + 1)
        password = getpass.getpass("PDF password (memory only): ") if args.password else ""
        result = run_extraction(data, args.statement.name, password, config=cfg)
    except (ExtractionError, OSError) as exc:
        print(
            str(exc) if isinstance(exc, ExtractionError) else "Cannot open the local file.",
            file=sys.stderr,
        )
        return 1
    for row in result["rows"]:
        # Escape terminal control sequences, not only browser HTML.
        print(json.dumps(row, ensure_ascii=True))
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
    print(
        "Private local output only. Compare every row with your file; "
        "no real-bank accuracy is implied."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
