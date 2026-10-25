"""Billing projections from chronological Decimal charges, independent of notice lifetime."""

from bisect import insort
from decimal import Decimal


def billing_projection(amounts, minimum_occurrences):
    """Use the latest price after a historical >5% increase; otherwise retain averages.

    Prefix medians match the detector's price rule at each eligible point in history.
    Keeping that evidence prevents an established new price reverting to an old mean
    when the previous-price median eventually catches up. Never infer actual usage.
    """
    previous = []
    established = False
    increased = False
    increase_streak = 0
    latest = None
    for amount in amounts:
        if not isinstance(amount, Decimal):
            raise TypeError("Billing amounts must be Decimal")
        increased = False
        if len(previous) >= minimum_occurrences - 1:
            middle = len(previous) // 2
            median = (
                previous[middle]
                if len(previous) % 2
                else (previous[middle - 1] + previous[middle]) / 2
            )
            increased = amount > median * Decimal("1.05")
        increase_streak = increase_streak + 1 if increased else 0
        # Repeated higher charges establish a price even with FX/usage variation.
        # A single spike does not permanently replace the averaging policy.
        established |= increase_streak >= 2
        insort(previous, amount)
        latest = amount
    return latest if established or increased else None
