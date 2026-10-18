import csv
import io
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.detector import detect_recurring
from app.services.ingestion import parse_csv
from scripts.evaluate_detector import evaluate, score
from scripts.gen_sample_data import generate_dataset, write_dataset

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.parametrize(
    ("csv_name", "truth_name"),
    [
        ("sample_transactions.csv", "ground_truth.json"),
        ("handwritten_bank.csv", "handwritten_bank_ground_truth.json"),
        ("handwritten_products.csv", "handwritten_products_ground_truth.json"),
    ],
)
def test_committed_datasets_meet_quality_gate(csv_name, truth_name):
    result = evaluate(DATA / csv_name, DATA / truth_name)
    assert result.f1 >= Decimal("0.9"), result
    assert not result.failures


def _detect_rows(rows, as_of):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["date", "description", "amount", "type"])
    writer.writeheader()
    writer.writerows(rows)
    parsed = parse_csv(buffer.getvalue().encode())
    assert not parsed.errors
    return detect_recurring(parsed.transactions, as_of=date.fromisoformat(as_of))


@pytest.mark.parametrize("seed", range(20))
def test_randomized_holdout_histories(seed):
    # These seeds are not the committed demo seed; both noise and FX/drift vary.
    rows, truth = generate_dataset(seed=seed)
    found = _detect_rows(rows, truth["as_of"])
    result = score(found, truth["patterns"])
    assert result.f1 >= Decimal("0.9"), result
    assert not result.failures


def test_generator_is_reproducible_and_labels_dont_use_detector(tmp_path):
    write_dataset(tmp_path, seed=42)
    first_csv = (tmp_path / "sample_transactions.csv").read_bytes()
    first_truth = (tmp_path / "ground_truth.json").read_bytes()
    write_dataset(tmp_path, seed=42)
    assert (tmp_path / "sample_transactions.csv").read_bytes() == first_csv
    assert (tmp_path / "ground_truth.json").read_bytes() == first_truth
    assert evaluate(tmp_path / "sample_transactions.csv", tmp_path / "ground_truth.json").f1 == 1


@pytest.mark.parametrize("as_of", [date(2026, 1, 1), date(2024, 2, 29), date(2027, 5, 1)])
def test_generation_at_month_boundaries_keeps_two_yearly_charges(as_of):
    rows, truth = generate_dataset(as_of=as_of)
    result = score(_detect_rows(rows, truth["as_of"]), truth["patterns"])
    assert result.f1 >= Decimal("0.9"), result
    assert not result.failures


def test_wrong_cadence_and_merged_products_reduce_metrics():
    rows, truth = generate_dataset()
    found = _detect_rows(rows, truth["as_of"])
    apple = [d for d in found if d.merchant == "apple"]
    assert len(apple) == 2
    corrupted = [d for d in found if d != apple[0]]
    corrupted[0] = replace(corrupted[0], cadence="weekly")
    result = score(corrupted, truth["patterns"])
    assert result.false_negative == 2
    assert result.false_positive == 1
    assert result.f1 < 1
    assert result.failures
