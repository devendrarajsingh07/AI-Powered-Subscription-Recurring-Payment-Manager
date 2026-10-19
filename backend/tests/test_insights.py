from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from app.services.insights import InsightInput, rules

DAY = date(2026, 10, 18)


def item(id="one", amount="100", **values):
    return InsightInput(
        id,
        "synthetic " + id,
        values.pop("category", "music"),
        values.pop("cadence", "monthly"),
        D(amount),
        **values,
    )


@pytest.mark.parametrize(
    "amounts, expected", [(["100", "150"], "100.00"), (["100", "150", "200"], "250.00")]
)
def test_duplicate_sum_except_most_expensive(amounts, expected):
    result = rules([item(str(i), amount) for i, amount in enumerate(amounts)], as_of=DAY)
    duplicate = next(r for r in result if r.type == "duplicate")
    assert duplicate.est_monthly_saving == D(expected)
    assert "You may want to review" in duplicate.message


@pytest.mark.parametrize(
    "values", [dict(kind="fixed_bill"), dict(status="cancelled"), dict(status="dismissed")]
)
def test_exclusions(values):
    assert not rules([item(**values), item("two")], as_of=DAY)


@pytest.mark.parametrize("annual, count", [("11999.99", 0), ("12000.00", 0), ("12000.01", 1)])
def test_high_cost_boundary_no_estimate(annual, count):
    result = rules([item(amount=annual, cadence="yearly")], as_of=DAY)
    assert len(result) == count
    if result:
        assert result[0].est_monthly_saving is None


def test_share_requires_above_median_and_threshold():
    result = rules(
        [item("one", "100", category="software"), item("two", "900", category="software")],
        as_of=DAY,
        yearly_threshold=D("99999"),
        share_threshold=D("0.5"),
    )
    assert [r.subscription_id for r in result] == ["two"]


def test_price_increase_extra_cost_not_saving():
    result = rules(
        [item(cadence="yearly", price_previous_amount=D("100"), price_new_amount=D("112"))],
        as_of=DAY,
    )
    assert len(result) == 1
    assert result[0].extra_monthly_cost == D("1.00")
    assert result[0].percent_change == D("12.00")
    assert result[0].est_monthly_saving is None


@pytest.mark.parametrize("days, unused", [(None, False), (59, False), (60, False), (61, True)])
def test_usage_needs_user_signal(days, unused):
    result = rules([item(last_used_at=DAY - timedelta(days=days) if days else None)], as_of=DAY)
    assert bool([r for r in result if r.type == "possibly_unused"]) is unused


def test_clock_is_not_material_to_unused_facts():
    sub = item(last_used_at=DAY - timedelta(days=90))
    first = rules([sub], as_of=DAY)[0]
    assert first.facts_hash == rules([sub], as_of=DAY + timedelta(days=1))[0].facts_hash
    assert first.facts_hash != rules([replace(sub, avg_amount=D("101"))], as_of=DAY)[0].facts_hash
