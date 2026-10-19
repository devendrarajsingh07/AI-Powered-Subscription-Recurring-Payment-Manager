"""Seven read-only tools. Identity is bound by the server, never a model argument."""

import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app import models as m
from app import repositories as repo
from app.schemas import Category, RecommendationStatus, Status
from app.services.insights import potential_savings
from app.services.renewals import sub_out, upcoming
from app.services.summary import ZERO, equivalents, money, summarize

CAP = 30


def clean(value, limit=160):
    value = "".join(c for c in str(value) if not unicodedata.category(c).startswith("C"))
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]+", "[redacted]", value)
    value = re.sub(r"\b(?:sk-[\w-]+|eyJ[\w.-]{20,})\b", "[redacted]", value)
    return value[:limit]


def data_text(value):
    return {"data_text": clean(value), "untrusted": True}


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListArgs(Args):
    status: Status | None = None
    category: Category | None = None


class SpendArgs(Args):
    period: Literal["month", "year"]
    group_by: Literal["category", "merchant"] | None = None


class RenewalArgs(Args):
    days: StrictInt = Field(ge=1, le=365)


class RecommendationArgs(Args):
    status: RecommendationStatus | None = None


class DetailArgs(Args):
    merchant: str = Field(min_length=1, max_length=160)


SCHEMAS = {
    "list_subscriptions": ListArgs,
    "spend_summary": SpendArgs,
    "upcoming_renewals": RenewalArgs,
    "compare_to_budget": Args,
    "get_recommendations": RecommendationArgs,
    "subscription_detail": DetailArgs,
    "potential_savings": Args,
}


def definitions():
    return [
        dict(
            name=name,
            description=name.replace("_", " ") + " from signed-in data only",
            input_schema=schema.model_json_schema(),
        )
        for name, schema in SCHEMAS.items()
    ]


def subscription(row, as_of):
    item = sub_out(row, as_of=as_of)
    month, year = equivalents(item.avg_amount, item.cadence)
    return dict(
        merchant=data_text(item.merchant),
        category=item.category,
        kind=item.kind,
        cadence=item.cadence,
        amount=item.avg_amount,
        monthly_equivalent=money(month),
        yearly_total=money(year),
        currency=item.currency,
        status=item.status,
        next_expected=item.next_expected,
        last_charge=item.last_charge,
        confidence_percent=money(item.confidence * 100),
        possibly_cancelled=item.possibly_cancelled,
        requires_confirmation=item.requires_confirmation,
        missed_cycles=item.missed_cycles,
        occurrences=item.occurrences,
        previous_amount=item.price_increase.previous_amount if item.price_increase else None,
        new_amount=item.price_increase.new_amount if item.price_increase else None,
    )


def envelope(data, as_of):
    figures = dict(amounts=[], counts=[], dates=[], percentages=[])

    def convert(value, key=""):
        if isinstance(value, dict):
            if "data_text" in value:
                return value  # Merchant numbers cannot authorize answer figures.
            return {name: convert(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [convert(item, key) for item in value]
        if isinstance(value, Decimal):
            result = format(value, ".2f")
            figures["percentages" if "percent" in key else "amounts"].append(result)
            return result
        if isinstance(value, date):
            result = value.isoformat()
            figures["dates"].append(result)
            return result
        if type(value) is int:
            figures["counts"].append(str(value))
        return value

    result = dict(as_of=as_of.isoformat(), data=convert(data), figures=figures)
    figures["dates"].append(as_of.isoformat())
    # List caps and bounded merchant strings keep the complete JSON valid (never slice JSON).
    if len(json.dumps(result)) > 60000:
        raise ValueError("Tool result exceeds safe size")
    return result


class ChatTools:
    def __init__(self, db, authenticated_id, as_of):
        self.db, self._identity, self.as_of = db, authenticated_id, as_of

    def invoke(self, name, arguments):
        args = SCHEMAS[name].model_validate(arguments)
        return envelope(getattr(self, name)(args), self.as_of)

    def list_subscriptions(self, args):
        filters = [
            getattr(m.Subscription, key) == value
            for key, value in args.model_dump().items()
            if value is not None
        ]
        rows = repo.list_owned(
            self.db,
            self._identity,
            m.Subscription,
            *filters,
            limit=None,
            order_by=m.Subscription.avg_amount.desc(),
        )
        plans = [row for row in rows if row.kind == "subscription"]
        most = (
            max(plans, key=lambda row: equivalents(row.avg_amount, row.cadence)[0])
            if plans
            else None
        )
        return dict(
            most_expensive=subscription(most, self.as_of) if most else None,
            count=len(rows),
            truncated=len(rows) > CAP,
            items=[subscription(row, self.as_of) for row in rows[:CAP]],
        )

    def spend_summary(self, args):
        result = summarize(self.db, self._identity, period=args.period)
        if args.group_by == "merchant":
            groups = {}
            for row in repo.active_subscriptions(self.db, self._identity):
                group = groups.setdefault(row.merchant, [ZERO, ZERO, 0])
                month, year = equivalents(row.avg_amount, row.cadence)
                group[0] += month
                group[1] += year
                group[2] += 1
            result["merchants"] = [
                dict(
                    merchant=data_text(name),
                    monthly_equivalent=money(v[0]),
                    yearly_total=money(v[1]),
                    count=v[2],
                )
                for name, v in sorted(groups.items())[:CAP]
            ]
            result["truncated"] = len(groups) > CAP
        return result

    def upcoming_renewals(self, args):
        rows = upcoming(self.db, self._identity, days=args.days, as_of=self.as_of)
        return dict(
            count=len(rows),
            truncated=len(rows) > CAP,
            items=[subscription(row, self.as_of) for row in rows[:CAP]],
        )

    def compare_to_budget(self, args):
        total = summarize(self.db, self._identity, period="month")["monthly_equivalent"]
        budgets = repo.list_owned(self.db, self._identity, m.Budget, limit=1)
        limit = budgets[0].monthly_limit if budgets else None
        return dict(
            monthly_total=total,
            monthly_limit=limit,
            currency="INR",
            overage=money(max(ZERO, total - limit)) if limit is not None else None,
            remaining=money(max(ZERO, limit - total)) if limit is not None else None,
        )

    def get_recommendations(self, args):
        conditions = [m.Recommendation.status == args.status] if args.status else []
        rows = repo.list_owned(self.db, self._identity, m.Recommendation, *conditions, limit=CAP)
        count = repo.count_owned(self.db, self._identity, m.Recommendation, *conditions)
        return dict(
            count=count,
            truncated=count > len(rows),
            currency="INR",
            items=[
                dict(
                    type=row.type,
                    status=row.status,
                    est_monthly_saving=row.est_monthly_saving,
                    extra_monthly_cost=row.extra_monthly_cost,
                    percent_change=row.percent_change,
                    members=[
                        dict(merchant=data_text(member["merchant"]), category=member["category"])
                        for member in row.facts.get("members", [])[:CAP]
                    ],
                )
                for row in rows
            ],
        )

    def subscription_detail(self, args):
        rows = repo.list_owned(self.db, self._identity, m.Subscription, limit=None)
        name = args.merchant.strip().casefold()
        exact = [row for row in rows if row.merchant.casefold() == name]
        matches = exact or [row for row in rows if row.merchant.casefold().startswith(name)]
        if len(matches) != 1:
            return dict(
                found=False,
                ambiguous=len(matches) > 1,
                count=len(matches),
                candidates=[subscription(row, self.as_of) for row in matches[:CAP]],
            )
        return dict(found=True, item=subscription(matches[0], self.as_of))

    def potential_savings(self, args):
        return dict(potential_savings=potential_savings(self.db, self._identity), currency="INR")
