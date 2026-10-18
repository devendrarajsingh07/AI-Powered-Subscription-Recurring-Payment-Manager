"""Evaluate independently labelled recurring products, including fixed bills and negatives.

Match one-to-one on normalized merchant + cadence + kind + currency + amount within one
paisa. Matching the wrong cadence, merging Apple products, and false positives all count.
Also check category, occurrence count, last charge, stopped flag, and price-increase signal
when specified. CSV errors are checked separately. Never derive expected labels from detection.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

# Support the requested `python scripts/evaluate_detector.py` entry point.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.detector import Detection, detect_recurring  # noqa: E402
from app.services.ingestion import parse_csv  # noqa: E402


@dataclass(frozen=True)
class Metrics:
    true_positive: int
    false_positive: int
    false_negative: int
    failures: tuple[str, ...] = ()

    @property
    def precision(self) -> Decimal:
        total = self.true_positive + self.false_positive
        return Decimal(self.true_positive) / total if total else Decimal(0)

    @property
    def recall(self) -> Decimal:
        total = self.true_positive + self.false_negative
        return Decimal(self.true_positive) / total if total else Decimal(0)

    @property
    def f1(self) -> Decimal:
        total = 2 * self.true_positive + self.false_positive + self.false_negative
        return Decimal(2 * self.true_positive) / total if total else Decimal(0)


def _matches(found: Detection, expected: dict) -> bool:
    return (
        found.merchant == expected["merchant"]
        and found.cadence == expected["cadence"]
        and found.kind == expected["kind"]
        and found.currency == expected.get("currency", "INR")
        and abs(found.avg_amount - Decimal(expected["avg_amount"])) <= Decimal("0.01")
    )


def score(detections: list[Detection], patterns: list[dict]) -> Metrics:
    unmatched = list(detections)
    matched = 0
    failures = []
    for expected in patterns:
        found = next((item for item in unmatched if _matches(item, expected)), None)
        if found is None:
            failures.append(
                f"Missed: {expected['merchant']} / {expected['cadence']} / {expected['avg_amount']}"
            )
            continue
        unmatched.remove(found)
        matched += 1
        for field in ("category", "occurrences", "last_charge", "possibly_cancelled"):
            if field in expected:
                actual = getattr(found, field)
                if isinstance(actual, date):
                    actual = actual.isoformat()
                if actual != expected[field]:
                    failures.append(
                        f"Attribute mismatch: {found.merchant} / {field}: "
                        f"expected {expected[field]}, got {actual}"
                    )
        if (
            "price_increase" in expected
            and bool(found.price_increase) != expected["price_increase"]
        ):
            failures.append(f"Price signal mismatch: {found.merchant}")
    for found in unmatched:
        failures.append(f"False positive: {found.merchant} / {found.cadence} / {found.avg_amount}")
    return Metrics(matched, len(unmatched), len(patterns) - matched, tuple(failures))


def evaluate(csv_path: Path, truth_path: Path) -> Metrics:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    parsed = parse_csv(csv_path.read_bytes())
    result = score(
        detect_recurring(parsed.transactions, as_of=date.fromisoformat(truth["as_of"])),
        truth["patterns"],
    )
    if parsed.skipped_count != truth.get("expected_skipped_rows", 0):
        return Metrics(
            result.true_positive,
            result.false_positive,
            result.false_negative,
            result.failures + (f"Unexpected skipped rows: {parsed.skipped_count}",),
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data"
    )
    parser.add_argument("--min-f1", type=Decimal, default=Decimal("0.9"))
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    if not Decimal(0) <= args.min_f1 <= Decimal(1):
        parser.error("--min-f1 must be between 0 and 1")
    suites = [
        ("Synthetic (seed 42)", "sample_transactions.csv", "ground_truth.json"),
        ("Handwritten bank", "handwritten_bank.csv", "handwritten_bank_ground_truth.json"),
        (
            "Handwritten products",
            "handwritten_products.csv",
            "handwritten_products_ground_truth.json",
        ),
    ]
    print("Dataset                    TP  FP  FN  Precision  Recall     F1")
    results = []
    passed = True
    for name, csv_name, truth_name in suites:
        try:
            result = evaluate(args.data_dir / csv_name, args.data_dir / truth_name)
        except (OSError, ValueError, KeyError) as exc:
            print(f"{name}: evaluation failed ({exc})")
            passed = False
            continue
        print(
            f"{name:26} {result.true_positive:2}  {result.false_positive:2}  "
            f"{result.false_negative:2}  {result.precision:.4f}     "
            f"{result.recall:.4f}  {result.f1:.4f}"
        )
        for failure in result.failures:
            print(f"  - {failure}")
        passed &= result.f1 >= args.min_f1 and not result.failures
        results.append(
            {
                "dataset": name,
                "true_positive": result.true_positive,
                "false_positive": result.false_positive,
                "false_negative": result.false_negative,
                "precision": str(result.precision),
                "recall": str(result.recall),
                "f1": str(result.f1),
                "failures": result.failures,
            }
        )
    if args.json_output:
        args.json_output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
