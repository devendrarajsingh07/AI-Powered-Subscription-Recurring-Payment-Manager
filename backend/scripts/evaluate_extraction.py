"""Measure synthetic field errors AND conservative review coverage; no real-bank claim."""

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.extraction_runner import run_extraction  # noqa: E402
from app.services.statement_extraction import ExtractionError  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data/extraction"


def same(expected, actual, key):
    if key == "amount":
        return actual.get(key) is not None and Decimal(expected[key]) == Decimal(actual[key])
    return expected[key] == actual.get(key)


def key(row):
    return row.get("date"), row.get("type"), Decimal(row["amount"]) if row.get("amount") else None


def evaluate():
    manifest = json.loads((DATA / "manifest.json").read_text())
    results = []
    for variant in manifest["variants"]:
        expected = variant["rows"]
        result, failure = None, None
        try:
            result = run_extraction(
                (DATA / variant["file"]).read_bytes(),
                variant["file"],
                variant.get("password", ""),
                config=get_settings(),
            )
        except ExtractionError as exc:
            failure = exc.code
        actual = result["rows"] if result else []
        matches = sum((Counter(map(key, expected)) & Counter(map(key, actual))).values())
        exact = {
            name: sum(same(e, a, name) for e, a in zip(expected, actual))
            for name in ("date", "amount", "description", "type")
        }
        wrong_unflagged = sum(
            not row["flags"]
            and (
                index >= len(expected)
                or not all(same(expected[index], row, name) for name in exact)
            )
            for index, row in enumerate(actual)
        )
        unflagged = sum(not row["flags"] for row in actual)
        metrics = dict(
            file=variant["file"],
            kind=variant["kind"],
            expected=len(expected),
            extracted=len(actual),
            precision=matches / len(actual) if actual else 0,
            recall=matches / len(expected),
            date_accuracy=exact["date"] / len(expected),
            amount_accuracy=exact["amount"] / len(expected),
            description_accuracy=exact["description"] / len(expected),
            field_accuracy=sum(exact.values()) / (4 * len(expected)),
            reconciliation=result["reconciliation"]["status"] if result else "rejected",
            flagged_rate=sum(bool(row["flags"]) for row in actual) / len(actual) if actual else 0,
            unflagged_rows=unflagged,
            silent_errors=wrong_unflagged,
            silent_error_rate=wrong_unflagged / unflagged if unflagged else 0,
            rejected=failure,
            expected_rejection=variant.get("reject", False),
            dpi=variant.get("dpi"),
        )
        results.append(metrics)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    results = evaluate()
    print(
        "Variant                     Rows  Precision Recall Date   Amount Desc   "
        "Flags  Reconciliation Silent"
    )
    for row in results:
        print(
            f"{row['file']:27} {row['extracted']:4}  {row['precision']:.3f}    "
            f"{row['recall']:.3f}  {row['date_accuracy']:.3f}  {row['amount_accuracy']:.3f}  "
            f"{row['description_accuracy']:.3f}  {row['flagged_rate']:.3f}  "
            f"{row['reconciliation']:14} {row['silent_errors']}"
        )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n")
    failed = any(
        row["silent_errors"]
        or row["kind"] == "text"
        and row["field_accuracy"] < 0.99
        or row["expected_rejection"]
        and not row["rejected"]
        for row in results
    )
    floor = [
        row
        for row in results
        if row["kind"] == "ocr"
        and row["dpi"]
        and row["recall"] >= 0.95
        and row["date_accuracy"] >= 0.95
        and row["amount_accuracy"] >= 0.95
    ]
    print(
        "Synthetic OCR quality floor (date/amount/row >=95%):",
        min((row["dpi"] for row in floor), default="none"),
        "dpi; no real-bank claim",
    )
    print("All OCR rows require explicit review; zero silent errors is NOT perfect OCR accuracy.")
    if failed:
        raise SystemExit(
            "Extraction gate failed: silent errors, clean-text accuracy<99%, "
            "or expected rejection missing"
        )


if __name__ == "__main__":
    main()
