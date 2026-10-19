"""Private local inspection: no database, provider, file output or personal-data logs."""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.detector import detect_recurring  # noqa: E402
from app.services.ingestion import CsvValidationError, parse_csv  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    # Bound reads before parsing. The file can live entirely outside this repository.
    with args.csv.open("rb") as stream:
        content = stream.read(5 * 1024 * 1024 + 1)
    try:
        parsed = parse_csv(content)
    except CsvValidationError as error:
        print("Could not parse:", str(error))
        return 1
    found = detect_recurring(parsed.transactions, as_of=args.as_of)
    print("Detected", len(found), "recurring products; malformed rows:", parsed.skipped_count)
    for item in found:
        print(item.merchant, item.cadence, item.avg_amount, "confidence", item.confidence)
    print("Compare with your known subscriptions; record misses and false positives locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
