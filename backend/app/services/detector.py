"""Pure recurrence detection. All money/statistics use Decimal, never binary floats."""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Sequence

from app.services.categories import categorize
from app.services.normalizer import normalize_merchant

CENT = Decimal("0.01")
ZERO = Decimal(0)
ONE = Decimal(1)
MAX_CV = Decimal("0.15")
CADENCES = {
    "weekly": (7, 1, 3),
    "monthly": (30, 4, 3),
    "quarterly": (91, 6, 3),
    "yearly": (365, 10, 2),
}


MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}


def step(start: date, cadence: str, cycles: int) -> date:
    """`cycles` billing periods after `start`: weekly by days, others by calendar month."""
    if cadence == "weekly":
        return start + timedelta(days=7 * cycles)
    total = start.month - 1 + MONTHS[cadence] * cycles
    year, month = start.year + total // 12, total % 12 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def project(last_charge: date, cadence: str, as_of: date) -> tuple[date, int]:
    """Next expected charge and missed cycles; always measured from the last real charge."""
    if step(last_charge, cadence, 1) >= as_of:
        return step(last_charge, cadence, 1), 0
    missed = 0
    while step(last_charge, cadence, missed + 1) < as_of:
        missed += 1
    return step(last_charge, cadence, missed + 1), missed


@dataclass(frozen=True)
class Transaction:
    date: date
    raw_description: str
    amount: Decimal
    type: Literal["debit", "credit"] = "debit"
    currency: str = "INR"
    id: str | int | None = None

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError("Transaction amounts must be Decimal")
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("Transaction amount must be finite and positive")
        if self.amount >= Decimal("10000000000") or self.amount != self.amount.quantize(CENT):
            raise ValueError("Transaction amount must fit NUMERIC(12,2)")
        if self.type not in ("debit", "credit"):
            raise ValueError("Transaction type must be debit or credit")


@dataclass(frozen=True)
class PriceIncrease:
    previous_median: Decimal
    latest_amount: Decimal
    percent: Decimal


@dataclass(frozen=True)
class Detection:
    merchant: str
    category: str
    kind: str
    cadence: str
    avg_amount: Decimal
    currency: str
    confidence: Decimal
    regularity: Decimal
    amount_cv: Decimal
    occurrences: int
    last_charge: date
    next_expected: date
    missed_cycles: int
    possibly_cancelled: bool
    requires_confirmation: bool
    price_increase: PriceIncrease | None
    charges: tuple[Transaction, ...]


def median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _candidate(charges: Sequence[Transaction], as_of: date) -> Detection | None:
    charges = tuple(sorted(charges, key=lambda tx: (tx.date, tx.amount, tx.raw_description)))
    if len(charges) < 2:
        return None
    intervals = [Decimal((b.date - a.date).days) for a, b in zip(charges, charges[1:])]
    interval_median = median(intervals)
    cadence = next(
        (
            name
            for name, (days, tolerance, _) in CADENCES.items()
            if abs(interval_median - days) <= tolerance
        ),
        None,
    )
    if cadence is None:
        return None
    days, tolerance, minimum = CADENCES[cadence]
    if len(charges) < minimum:
        return None
    regularity = Decimal(sum(abs(interval - days) <= tolerance for interval in intervals))
    regularity /= len(intervals)
    amounts = [tx.amount for tx in charges]
    mean = sum(amounts, ZERO) / len(amounts)
    cv = (sum(((amount - mean) ** 2 for amount in amounts), ZERO) / len(amounts)).sqrt() / mean
    if regularity < Decimal("0.7") or cv > MAX_CV:
        return None
    next_expected, missed = project(charges[-1].date, cadence, as_of)
    confidence = (
        Decimal("0.5") * regularity
        + Decimal("0.3") * max(ZERO, ONE - cv / MAX_CV)
        + Decimal("0.2") * min(ONE, Decimal(len(charges)) / 6)
    )
    if cadence == "yearly":
        confidence *= Decimal("0.85")
    previous = median(amounts[:-1])
    increase = None
    if amounts[-1] > previous * Decimal("1.05"):
        increase = PriceIncrease(
            previous, amounts[-1], ((amounts[-1] / previous - ONE) * 100).quantize(CENT)
        )
    merchant = normalize_merchant(charges[0].raw_description)
    category = categorize(merchant, tuple(tx.raw_description for tx in charges))
    return Detection(
        merchant,
        category.name,
        category.kind,
        cadence,
        mean.quantize(CENT, rounding=ROUND_HALF_UP),
        charges[0].currency,
        confidence.quantize(Decimal("0.001")),
        regularity,
        cv,
        len(charges),
        charges[-1].date,
        next_expected,
        missed,
        missed >= 2,
        category.requires_confirmation,
        increase,
        charges,
    )


def _amount_clusters(charges: Sequence[Transaction]) -> list[list[Transaction]]:
    clusters: list[list[Transaction]] = []
    for charge in sorted(charges, key=lambda tx: tx.amount):
        center = ZERO
        if clusters:
            ordered = clusters[-1]  # Already sorted: compute its median in constant time.
            middle = len(ordered) // 2
            center = (
                ordered[middle].amount
                if len(ordered) % 2
                else (ordered[middle - 1].amount + ordered[middle].amount) / 2
            )
        if not clusters or charge.amount > center * (ONE + MAX_CV):
            clusters.append([charge])
        else:
            clusters[-1].append(charge)
    return clusters


def detect_recurring(transactions: Sequence[Transaction], *, as_of: date) -> list[Detection]:
    """Explicit as_of makes results reproducible. Future charges and credits are excluded.

    Try the full history first so a price change is not split into a second product.
    If that fails, test amount clusters independently. This conservatively misses products
    with inseparable prices; such ambiguous detections require user review in later phases.
    """
    grouped: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    seen = set()
    for tx in transactions:
        key = (tx.date, tx.raw_description, tx.amount, tx.type, tx.currency)
        if tx.type != "debit" or tx.date > as_of or key in seen:
            continue
        seen.add(key)
        merchant = normalize_merchant(tx.raw_description)
        if merchant != "unknown":
            grouped[merchant, tx.currency].append(tx)
    detections = []
    for charges in grouped.values():
        whole = _candidate(charges, as_of)
        if whole:
            detections.append(whole)
            continue
        clusters = _amount_clusters(charges)
        if len(clusters) > 1:
            for cluster in clusters:
                candidate = _candidate(cluster, as_of)
                if candidate:
                    detections.append(candidate)
    return sorted(detections, key=lambda item: (item.merchant, item.currency, item.avg_amount))
