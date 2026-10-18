from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.detector import Transaction, detect_recurring
from app.services.normalizer import normalize_merchant, safe_display


def history(merchant="Netflix", amounts=("199",) * 6, start=date(2026, 1, 1), step=30):
    return [
        Transaction(start + timedelta(days=step * i), f"UPI/{merchant}/REF{i:08d}", Decimal(amount))
        for i, amount in enumerate(amounts)
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("UPI/NETFLIX.COM/987654321/BANGALORE", "netflix"),
        ("POS GOOGLE*YOUTUBE PREMIUM 1234 Mumbai", "youtube premium"),
        ("ACH APPLE.COM/BILL 8342", "apple"),
        ("NEFT ACME SOFTWARE PVT LTD REF83932 DELHI", "acme software"),
        ("IMPS/SPOTIFY/AB123456789/OKHDFCBANK", "spotify"),
        ("UPI RENT MUMBAI 123456", "rent"),
        ("POS 12345 BILL COM", "unknown"),
    ],
)
def test_normalization(raw, expected):
    assert normalize_merchant(raw) == expected


def test_month_end_drift_and_prediction():
    dates = [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    txs = [Transaction(day, "POS NETFLIX.COM", Decimal("199")) for day in dates]
    (item,) = detect_recurring(txs, as_of=date(2026, 5, 1))
    assert item.cadence == "monthly"
    assert item.next_expected == date(2026, 5, 30)
    assert item.regularity == 1
    assert item.avg_amount == Decimal("199.00")


def test_fx_amounts_use_decimal():
    (item,) = detect_recurring(
        history(amounts=("799.12", "815.20", "795.00", "830.41")), as_of=date(2026, 4, 5)
    )
    assert item.avg_amount == Decimal("809.93")
    assert item.amount_cv < Decimal("0.15")
    assert isinstance(item.confidence, Decimal)


def test_two_products_under_apple_are_amount_clustered():
    txs = history("APPLE.COM BILL", ("75",) * 6) + history("APPLE.COM BILL", ("119",) * 6)
    found = detect_recurring(txs, as_of=date(2026, 6, 1))
    assert [(d.merchant, d.avg_amount) for d in found] == [
        ("apple", Decimal("75.00")),
        ("apple", Decimal("119.00")),
    ]
    assert all(d.occurrences == 6 and d.requires_confirmation for d in found)


@pytest.mark.parametrize("merchant", ["Zomato", "Swiggy", "Uber", "Ola"])
def test_irregular_repeats_not_subscriptions(merchant):
    dates = [0, 1, 5, 17, 18, 45, 51, 78, 79, 81, 120]
    txs = [
        Transaction(date(2026, 1, 1) + timedelta(days=offset), merchant, Decimal("199"))
        for offset in dates
    ]
    assert detect_recurring(txs, as_of=date(2026, 6, 1)) == []


def test_two_yearly_charges_lower_confidence():
    (annual,) = detect_recurring(
        history("Microsoft", ("4899",) * 2, step=365), as_of=date(2027, 1, 2)
    )
    (monthly,) = detect_recurring(history(), as_of=date(2026, 6, 1))
    assert annual.cadence == "yearly"
    assert annual.next_expected == date(2028, 1, 1)
    assert annual.confidence < monthly.confidence


@pytest.mark.parametrize(("step", "cadence"), [(7, "weekly"), (91, "quarterly")])
def test_other_cadences(step, cadence):
    (item,) = detect_recurring(history(step=step), as_of=date(2028, 1, 1))
    assert item.cadence == cadence


@pytest.mark.parametrize("count", [1, 2])
def test_monthly_minimum_occurrences(count):
    assert detect_recurring(history(amounts=("199",) * count), as_of=date(2026, 6, 1)) == []


def test_stopped_subscription_is_uncertain_and_rolls_forward():
    (item,) = detect_recurring(history(), as_of=date(2026, 10, 18))
    assert item.possibly_cancelled
    assert item.missed_cycles >= 2
    assert item.next_expected >= date(2026, 10, 18)
    assert item.next_expected < date(2026, 10, 18) + timedelta(days=30)


def test_renewal_due_today_is_not_missed():
    (item,) = detect_recurring(history(), as_of=date(2026, 6, 30))
    assert item.next_expected == date(2026, 6, 30)
    assert item.missed_cycles == 0


def test_salary_credits_ignored():
    txs = [Transaction(tx.date, "Salary", tx.amount, "credit") for tx in history()]
    assert detect_recurring(txs, as_of=date(2026, 6, 1)) == []


@pytest.mark.parametrize("merchant", ["Rent", "Loan EMI", "LIC insurance", "Electricity"])
def test_fixed_bills_are_not_subscriptions(merchant):
    (item,) = detect_recurring(history(merchant), as_of=date(2026, 6, 1))
    assert item.kind == "fixed_bill"
    assert not item.requires_confirmation


def test_unknown_category_requires_confirmation_and_raw_is_untouched():
    txs = history("=UNKNOWN SERVICE")
    (item,) = detect_recurring(txs, as_of=date(2026, 6, 1))
    assert item.requires_confirmation
    assert item.category == "unknown"
    assert item.charges[0].raw_description == txs[0].raw_description


def test_price_change_not_split_as_product():
    (item,) = detect_recurring(
        history("Spotify", ("149",) * 4 + ("179",) * 2), as_of=date(2026, 6, 1)
    )
    assert item.occurrences == 6
    assert item.price_increase is not None
    assert item.price_increase.previous_median == Decimal("149")
    assert item.price_increase.latest_amount == Decimal("179")
    assert item.price_increase.percent == Decimal("20.13")


def test_exactly_five_percent_is_not_an_increase():
    (item,) = detect_recurring(
        history(amounts=("100", "100", "100", "105")), as_of=date(2026, 4, 5)
    )
    assert item.price_increase is None


@pytest.mark.parametrize(("low", "high", "expected"), [("85", "115", True), ("84", "116", False)])
def test_cv_boundary(low, high, expected):
    found = detect_recurring(history(amounts=(low, high, low, high)), as_of=date(2026, 4, 5))
    assert bool(found) is expected


@pytest.mark.parametrize(("regular_count", "expected"), [(7, True), (6, False)])
def test_regularity_boundary(regular_count, expected):
    intervals = [30] * regular_count + [18] * (10 - regular_count)
    days = [date(2026, 1, 1)]
    for interval in intervals:
        days.append(days[-1] + timedelta(days=interval))
    txs = [Transaction(day, "Netflix", Decimal("199")) for day in days]
    assert bool(detect_recurring(txs, as_of=date(2027, 1, 1))) is expected


def test_currency_groups_never_mix():
    txs = history() + [
        Transaction(tx.date, tx.raw_description, Decimal("2.99"), currency="USD")
        for tx in history()
    ]
    assert {d.currency for d in detect_recurring(txs, as_of=date(2026, 6, 1))} == {"INR", "USD"}


def test_future_transactions_excluded_and_exact_duplicates_dont_add_evidence():
    txs = history(amounts=("199",) * 3)
    assert detect_recurring(txs * 2, as_of=date(2026, 2, 1)) == []
    found = detect_recurring(txs * 2, as_of=date(2026, 4, 1))
    assert found[0].occurrences == 3


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", " \t=+-@"])
def test_csv_injection_is_neutralized_only_for_display(prefix):
    assert safe_display(prefix + "merchant") == "merchant"


@pytest.mark.parametrize(
    "amount",
    [1.25, "12.00", Decimal("NaN"), Decimal("-1"), Decimal("1.001"), Decimal("10000000000")],
)
def test_invalid_amounts_rejected(amount):
    with pytest.raises((TypeError, ValueError)):
        Transaction(date(2026, 1, 1), "Netflix", amount)
