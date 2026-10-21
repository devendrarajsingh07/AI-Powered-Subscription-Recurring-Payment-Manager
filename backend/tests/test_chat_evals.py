"""Known-answer expectations use ground-truth labels and independent arithmetic only."""

import json
import os
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from test_api import DATA, account, load

from app.config import get_settings

QUESTIONS = [
    "what renews this week?",
    "what renews in the next 30 days?",
    "what is my monthly total?",
    "what is my yearly total?",
    "how much do I spend on streaming per year?",
    "count of active subscriptions",
    "which subscriptions are duplicates?",
    "compare my budget",
    "most expensive subscription",
    "show a price increase",
    "which subscriptions are possibly cancelled?",
    "fixed bills vs subscriptions spend",
    "tell me about apple",
    "tell me about missing merchant",
    "what is the weather?",
    "potential savings",
    "cloud yearly spend",
    "yearly spend by category",
]


def answer(client, headers, question, **extra):
    response = client.post("/api/v1/chat", headers=headers, json={"message": question, **extra})
    assert response.status_code == 200, response.text
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        events.append((lines[0][7:], json.loads(lines[1][6:])))
    assert events[-1][0] == "final", events
    return events[-1][1], events


def expected():
    truth = json.loads((DATA / "ground_truth.json").read_text())
    patterns = truth["patterns"]
    factors = {
        "weekly": Decimal(52),
        "monthly": Decimal(12),
        "quarterly": Decimal(4),
        "yearly": Decimal(1),
    }
    nominal = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}
    day = date.fromisoformat(truth["as_of"])

    def rounded(value):
        return value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

    def annual(rows):
        return sum((Decimal(p["avg_amount"]) * factors[p["cadence"]] for p in rows), Decimal(0))

    def renewal(p):
        nxt = date.fromisoformat(p["last_charge"]) + timedelta(days=nominal[p["cadence"]])
        while nxt < day:
            nxt += timedelta(days=nominal[p["cadence"]])
        return nxt

    duplicates = {
        category: rounded(sum(costs) - max(costs))
        for category in ("music", "streaming", "cloud")
        for costs in [
            [
                Decimal(p["avg_amount"]) * factors[p["cadence"]] / 12
                for p in patterns
                if p["category"] == category and p["kind"] == "subscription"
            ]
        ]
    }
    month, year = rounded(annual(patterns) / 12), rounded(annual(patterns))
    allowed_money = {
        month,
        year,
        Decimal("1000.00"),
        month - Decimal("1000.00"),
        Decimal("0.00"),
        *duplicates.values(),
        sum(duplicates.values()),
    }
    for p in patterns:
        allowed_money.update(
            [Decimal(p["avg_amount"]), rounded(annual([p])), rounded(annual([p]) / 12)]
        )
        if p["price_increase"]:
            previous, new = Decimal(p["previous_amount"]), Decimal(p["new_amount"])
            allowed_money.update(
                [previous, new, rounded((new - previous) * factors[p["cadence"]] / 12)]
            )
    for kind in ("subscription", "fixed_bill"):
        rows = [p for p in patterns if p["kind"] == kind]
        allowed_money.update([rounded(annual(rows)), rounded(annual(rows) / 12)])
    for category in {p["category"] for p in patterns}:
        rows = [p for p in patterns if p["category"] == category]
        allowed_money.update([rounded(annual(rows)), rounded(annual(rows) / 12)])
    return locals()


def run_known_answers(client, headers):
    e = expected()
    rows, day = e["patterns"], e["day"]
    outputs, failures = [], []
    for question in QUESTIONS:
        result = None
        try:
            result, events = answer(client, headers, question)
            text = result["answer"]
            assert result["verified"], (question, result)
            assert not any(kind == "token" for kind, _ in events)
            # Independently parse every displayed amount/date, never calling the verifier/tools.
            figures = {Decimal(value) for value in re.findall(r"₹(-?\d+\.\d+)", text)}
            assert figures <= e["allowed_money"], (question, figures - e["allowed_money"])
            dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", text))
            assert dates <= {p["last_charge"] for p in rows} | {
                e["renewal"](p).isoformat() for p in rows
            }
            if "renews" in question:
                days = 7 if "week" in question else 30
                due = [p for p in rows if e["renewal"](p) <= day + timedelta(days=days)]
                assert dates == {e["renewal"](p).isoformat() for p in due}
                assert figures == {Decimal(p["avg_amount"]) for p in due}
            if "monthly total" in question:
                assert f"₹{e['month']:.2f}" in text
            if "yearly total" in question:
                assert f"₹{e['year']:.2f}" in text
            if "streaming per year" in question or question == "cloud yearly spend":
                category = "streaming" if "streaming" in question else "cloud"
                value = e["rounded"](e["annual"]([p for p in rows if p["category"] == category]))
                assert f"₹{value:.2f}" in text
            if question == "count of active subscriptions":
                assert int(re.search(r": (\d+)", text)[1]) == sum(
                    p["kind"] == "subscription" for p in rows
                )
            if "duplicates" in question:
                assert figures == set(e["duplicates"].values())
            if question == "compare my budget":
                assert f"₹{e['month'] - Decimal('1000'):.2f}" in text
            if question == "most expensive subscription":
                most = max(
                    (p for p in rows if p["kind"] == "subscription"),
                    key=lambda p: e["annual"]([p]) / 12,
                )
                assert most["merchant"] in text
            if "price increase" in question:
                p = next(p for p in rows if p["price_increase"])
                percent = e["rounded"](
                    (Decimal(p["new_amount"]) - Decimal(p["previous_amount"]))
                    / Decimal(p["previous_amount"])
                    * 100
                )
                assert re.findall(r"(\d+\.\d+)%", text) == [str(percent)]
            if "possibly cancelled" in question:
                assert all(p["merchant"] in text for p in rows if p["possibly_cancelled"])
            if "fixed bills" in question:
                value = e["rounded"](
                    e["annual"]([p for p in rows if p["kind"] == "fixed_bill"]) / 12
                )
                assert f"₹{value:.2f}" in text
            if question == "tell me about apple":
                assert "ambiguous" in text and "cloud" in text and "music" in text
            if question in ("tell me about missing merchant", "what is the weather?"):
                assert "I don't have" in text
            if question == "potential savings":
                assert f"₹{sum(e['duplicates'].values()):.2f}" in text
            if question == "yearly spend by category":
                category_totals = [
                    e["annual"]([p for p in rows if p["category"] == category])
                    for category in {p["category"] for p in rows}
                ]
                assert figures == {
                    value
                    for total in category_totals
                    for value in (e["rounded"](total), e["rounded"](total / 12))
                }
            outputs.append((question, result["verified"]))

        except AssertionError:
            failures.append(question)
            blocked = result is not None and not result["verified"]
            print(
                "FAIL | "
                + question
                + (" | verifier blocked" if blocked else " | expected-value check")
            )
        else:
            print("PASS | " + question + " | figures verified")
    assert not failures, "Known-answer failures: " + ", ".join(failures)
    return outputs


def test_eighteen_known_answers_after_real_upload(api_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "chat_minute_limit", 100)
    headers, _ = account(api_client)
    if os.environ.get("SUBTRACK_LIVE_EVAL") == "1":
        assert get_settings().llm_provider == "gemini", "Live eval requires the Gemini provider"
        api_client.put("/api/v1/chat/config", headers=headers, json={"live_opt_in": True})
    load(api_client, headers)
    assert (
        api_client.put(
            "/api/v1/budget", headers=headers, json={"monthly_limit": "1000.00"}
        ).status_code
        == 200
    )
    assert len(run_known_answers(api_client, headers)) >= 15
