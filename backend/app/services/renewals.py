"""Shared API/tool renewal projection. No persistence or implicit clock."""

from datetime import timedelta

from app import repositories as repo
from app import schemas as s
from app.services.detector import project


def sub_out(record, *, as_of=None):
    result = s.SubscriptionOut.model_validate(record)
    if not isinstance(record, s.SubscriptionOut) and record.price_previous_amount is not None:
        result.price_increase = s.PriceIncreaseOut(
            previous_amount=record.price_previous_amount,
            new_amount=record.price_new_amount,
            detected_on=record.price_detected_on,
        )
    if as_of is not None:
        result.next_expected, missed = project(record.last_charge, record.cadence, as_of)
        result.missed_cycles, result.possibly_cancelled = missed, missed >= 2
    return result


def upcoming(db, user_id, *, days, as_of):
    items = [sub_out(row, as_of=as_of) for row in repo.active_subscriptions(db, user_id)]
    return sorted(
        (item for item in items if item.next_expected <= as_of + timedelta(days=days)),
        key=lambda item: (item.next_expected, item.merchant, str(item.id)),
    )
