"""Generate reproducible synthetic INR history and independent plan-level ground truth."""

import argparse
import calendar
import csv
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


@dataclass(frozen=True)
class Plan:
    merchant: str
    description: str
    amount: str
    category: str
    cadence: str = "monthly"
    kind: str = "subscription"
    fx: bool = False
    stopped: bool = False
    price_increase: bool = False


PLANS = (
    Plan("netflix", "NETFLIX.COM", "199", "streaming", price_increase=True),
    Plan("spotify", "SPOTIFY INDIA", "119", "music"),
    Plan("youtube premium", "GOOGLE YOUTUBE PREMIUM", "149", "streaming"),
    Plan("apple", "APPLE ICLOUD COM BILL", "75", "cloud"),
    Plan("apple", "APPLE MUSIC COM BILL", "119", "music"),
    Plan("google one", "GOOGLE ONE STORAGE", "130", "cloud"),
    Plan("cultfit", "CULT FIT", "1200", "fitness", stopped=True),
    Plan("airtel", "AIRTEL RECHARGE", "299", "telecom"),
    Plan("adobe", "ADOBE CREATIVE CLOUD", "699", "software", fx=True),
    Plan("microsoft", "MICROSOFT OFFICE", "4899", "software", cadence="yearly"),
    Plan("newspaper", "NEWSPAPER", "49", "news", cadence="weekly"),
    Plan("notion", "NOTION SOFTWARE", "1200", "software", cadence="quarterly"),
    Plan("rent", "RENT", "15000", "rent", kind="fixed_bill"),
    Plan("loan emi", "LOAN EMI", "4500", "loan", kind="fixed_bill"),
    Plan(
        "lic insurance", "LIC INSURANCE", "12000", "insurance", cadence="yearly", kind="fixed_bill"
    ),
    Plan("electricity", "ELECTRICITY", "1800", "utilities", kind="fixed_bill", fx=True),
)


def _month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def generate_dataset(*, seed: int = 42, as_of: date = date(2026, 10, 18)):
    if as_of.year < 2:
        raise ValueError("as_of must allow at least one preceding year of history")
    rng = random.Random(seed)
    month_index = as_of.year * 12 + as_of.month - 1 - 9
    first_year, first_month = divmod(month_index, 12)
    start = date(first_year, first_month + 1, 1)
    rows, truth = [], []
    for index, plan in enumerate(PLANS):
        if plan.cadence == "yearly":
            recent = _month_day(as_of.year, as_of.month, min(2, as_of.day))
            dates = [_month_day(recent.year - 1, recent.month, recent.day), recent]
        elif plan.cadence == "weekly":
            dates = [start + timedelta(days=7 * i) for i in range((as_of - start).days // 7 + 1)]
        elif plan.cadence == "quarterly":
            dates = [start + timedelta(days=91 * i) for i in range(4)]
        else:
            day = (index * 3) % 14 + 1
            dates = []
            for i in range(10):
                year, month = divmod(month_index + i, 12)
                billing_day = max(1, day + rng.choice([-1, 0, 0, 1]))
                dates.append(_month_day(year, month + 1, billing_day))
        dates = [day for day in dates if day <= as_of]
        if plan.stopped:
            dates = [day for day in dates if day < start + timedelta(days=180)]
        amounts = []
        for i, day in enumerate(dates):
            amount = Decimal(plan.amount)
            if plan.fx:
                amount *= Decimal(10000 + rng.randint(-200, 200)) / 10000
            if plan.price_increase and i >= len(dates) - 2:
                amount += Decimal("20")
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            amounts.append(amount)
            reference = rng.randint(100000000, 999999999)
            description = (
                f"{rng.choice(['UPI', 'POS', 'ACH'])}/{plan.description}/{reference}/MUMBAI"
            )
            rows.append(
                {
                    "date": day.isoformat(),
                    "description": description,
                    "amount": str(amount),
                    "type": "debit",
                }
            )
        truth.append(
            {
                "merchant": plan.merchant,
                "cadence": plan.cadence,
                "kind": plan.kind,
                "category": plan.category,
                "currency": "INR",
                "avg_amount": str(
                    (sum(amounts) / len(amounts)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "occurrences": len(dates),
                "last_charge": dates[-1].isoformat(),
                "possibly_cancelled": plan.stopped,
                "price_increase": plan.price_increase,
            }
        )
    # Independent irregular merchants and salary traps. No detector code is imported here.
    for merchant, count in (("ZOMATO", 72), ("SWIGGY", 48), ("UBER", 65), ("AMAZON SHOPPING", 35)):
        for _ in range(count):
            charged_on = start + timedelta(days=rng.randint(0, (as_of - start).days))
            amount = Decimal(rng.randint(8000, 155000)) / 100
            rows.append(
                {
                    "date": charged_on.isoformat(),
                    "description": f"UPI/{merchant}/REF{rng.randint(10000000, 99999999)}",
                    "amount": str(amount),
                    "type": "debit",
                }
            )
    for i in range(10):
        year, month = divmod(month_index + i, 12)
        rows.append(
            {
                "date": date(year, month + 1, 1).isoformat(),
                "description": f"NEFT SALARY REF{100000000 + i}",
                "amount": "85000.00",
                "type": "credit",
            }
        )
    for i in range(3):
        rows.append(
            {
                "date": (start + timedelta(days=30 * i)).isoformat(),
                "description": f"NETFLIX REFUND REF{200000000 + i}",
                "amount": "199.00",
                "type": "credit",
            }
        )
    rng.shuffle(rows)
    return rows, {
        "seed": seed,
        "as_of": as_of.isoformat(),
        "patterns": truth,
        "expected_skipped_rows": 0,
        "note": "Synthetic only; two yearly charges include one historical out-of-window row.",
    }


def write_dataset(output: Path, *, seed: int = 42, as_of: date = date(2026, 10, 18)):
    output.mkdir(parents=True, exist_ok=True)
    rows, truth = generate_dataset(seed=seed, as_of=as_of)
    with (output / "sample_transactions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "description", "amount", "type"])
        writer.writeheader()
        writer.writerows(rows)
    (output / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 18))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    print(f"Wrote {write_dataset(args.output, seed=args.seed, as_of=args.as_of)} synthetic rows")


if __name__ == "__main__":
    main()
