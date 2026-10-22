"""Calendar renewals, proxy-aware limiter address and database driver normalization."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.rate_limits import client_address
from app.services.detector import project, step
from app.services.summary import current_amount


def request(peer="10.0.0.1", forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


@pytest.mark.parametrize(
    "url",
    ["postgres://u@h/db", "postgresql://u@h/db", "postgresql+psycopg://u@h/db"],
)
def test_database_url_always_uses_psycopg_driver(url):
    assert Settings(database_url=url).database_url == "postgresql+psycopg://u@h/db"


def test_monthly_steps_use_calendar_months_without_drift():
    assert step(date(2026, 1, 31), "monthly", 1) == date(2026, 2, 28)
    assert step(date(2026, 1, 31), "monthly", 2) == date(2026, 3, 31)
    assert step(date(2026, 1, 15), "monthly", 12) == date(2027, 1, 15)
    assert step(date(2024, 2, 29), "yearly", 1) == date(2025, 2, 28)
    assert step(date(2026, 11, 30), "quarterly", 1) == date(2027, 2, 28)
    assert step(date(2026, 1, 1), "weekly", 2) == date(2026, 1, 15)


def test_projection_counts_missed_calendar_cycles():
    assert project(date(2026, 1, 15), "monthly", date(2026, 2, 1)) == (date(2026, 2, 15), 0)
    assert project(date(2026, 1, 15), "monthly", date(2026, 2, 15)) == (date(2026, 2, 15), 0)
    assert project(date(2026, 1, 15), "monthly", date(2026, 4, 20)) == (date(2026, 5, 15), 3)
    assert project(date(2026, 1, 1), "weekly", date(2026, 1, 20)) == (date(2026, 1, 22), 2)


def test_twelve_monthly_renewals_land_on_the_same_day_next_year():
    last = date(2026, 3, 10)
    assert project(last, "monthly", date(2027, 3, 10))[0] == date(2027, 3, 10)


def test_current_amount_uses_latest_price_only_after_an_increase():
    changed = SimpleNamespace(
        avg_amount=Decimal("203"),
        price_previous_amount=Decimal("199"),
        price_new_amount=Decimal("219"),
    )
    steady = SimpleNamespace(
        avg_amount=Decimal("119"), price_previous_amount=None, price_new_amount=None
    )
    assert current_amount(changed) == Decimal("219")
    assert current_amount(steady) == Decimal("119")


def test_forwarded_header_is_ignored_unless_proxies_are_trusted():
    spoofed = request(forwarded="1.2.3.4, 9.9.9.9")
    assert client_address(spoofed, 0) == "10.0.0.1"
    assert client_address(request(), 1) == "10.0.0.1"


def test_only_the_entry_added_by_trusted_proxies_is_used():
    chain = request(forwarded="6.6.6.6, 203.0.113.9")
    assert client_address(chain, 1) == "203.0.113.9"
    assert client_address(chain, 2) == "6.6.6.6"
    assert client_address(chain, 3) == "10.0.0.1"
    assert client_address(request(forwarded="not-an-ip"), 1) == "10.0.0.1"
