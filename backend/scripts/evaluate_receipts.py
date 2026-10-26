"""Offline field-accuracy gate against independent synthetic EML labels, not provider claims."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.email_receipts import ReceiptError, parse_receipt  # noqa: E402


def main():
    directory = Path(__file__).resolve().parents[1] / "data" / "receipts"
    truth = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    failed, reviewed, rejected = [], 0, 0
    for name, expected in truth["cases"].items():
        try:
            result = parse_receipt((directory / name).read_bytes())
        except ReceiptError as exc:
            correct = expected["verdict"] == "reject" and exc.code == expected["error"]
            rejected += 1
        else:
            row = result["rows"][0]
            correct = (
                expected["verdict"] == "review"
                and all(
                    row[key] == expected[key] for key in ("date", "description", "amount", "type")
                )
                and "email_review_required" in row["flags"]
            )
            reviewed += 1
        if not correct:
            failed.append(name)
    print(
        f"Synthetic EML fixtures: {len(truth['cases'])}; review: {reviewed}; rejected: {rejected}"
    )
    print(f"Exact labelled outcomes: {len(truth['cases']) - len(failed)}/{len(truth['cases'])}")
    print("Every candidate needs review. Real-provider receipt accuracy is not measured.")
    for name in failed:
        print(f"FAIL {name}")  # Synthetic filenames only, never receipt bodies or amounts.
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
