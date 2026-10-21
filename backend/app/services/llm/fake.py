"""Offline intent routing plus templates over actual tool output, no fixture figures."""

import json
import re

from app.schemas import Category
from app.services.grounding import render_data
from app.services.llm import Event, ToolCall


def quote_name(value):
    return json.dumps(value["data_text"], ensure_ascii=False)


def compose(data):
    """Only interpolate tool-provided fields; never aggregate or estimate."""
    if "monthly_total" in data:
        if data["monthly_limit"] is None:
            return (
                "Monthly recurring spend: ₹" + data["monthly_total"] + ". No budget is configured."
            )
        return (
            f"Monthly recurring spend: ₹{data['monthly_total']}. "
            f"Budget: ₹{data['monthly_limit']}. Overage: ₹{data['overage']}. "
            f"Remaining: ₹{data['remaining']}."
        )
    if "items" in data:
        lines = []
        for item in data["items"]:
            if item.get("type") == "duplicate":
                names = ", ".join(quote_name(m["merchant"]) for m in item["members"])
                category = item["members"][0]["category"]
                lines.append(
                    f"You may want to review {category} overlap: {names}. "
                    f"Estimated monthly saving: ₹{item['est_monthly_saving']}."
                )
            elif item.get("type") == "price_increase":
                names = ", ".join(quote_name(m["merchant"]) for m in item["members"])
                lines.append(
                    f"You may want to review {names}: {item['percent_change']}% "
                    f"price increase; extra monthly cost ₹{item['extra_monthly_cost']}."
                )
            elif "merchant" in item:
                lines.append(
                    f"{quote_name(item['merchant'])} ({item['category']}): "
                    f"₹{item['amount']} per charge; next expected {item['next_expected']}. "
                    + (
                        "May have stopped; you may want to review."
                        if item["possibly_cancelled"]
                        else ""
                    )
                )
            else:
                lines.extend(render_data([{"data": item}]).splitlines())
        return "\n".join(lines) if lines else "No matching items in the returned data."
    if "candidates" in data:
        return f"{data['count']} products match; choose a category or product:\n" + "\n".join(
            f"{quote_name(v['merchant'])} — {v['category']}, ₹{v['amount']}"
            for v in data["candidates"]
        )
    return render_data([{"data": data}])


class FakeLLM:
    def __init__(self, *, fabricate=False):
        from app.config import get_settings

        if fabricate and get_settings().environment == "production":
            raise RuntimeError("Adversarial FakeLLM is test-only")
        self.fabricate = fabricate

    async def categorize(self, merchant):
        return None  # Offline mode makes no external category suggestion.

    async def stream(self, *, system, messages, tools, force_final=False):
        results = []
        for message in reversed(messages):
            content = message["content"]
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        results.append(json.loads(block["content"]))
                if results:
                    break
        question = next(
            (
                m["content"].lower()
                for m in reversed(messages)
                if m["role"] == "user" and isinstance(m["content"], str)
            ),
            "",
        )
        if results:
            data = results[0]["data"]
            if "found" in data and not data["found"] and not data["ambiguous"]:
                text = "I don't have that information about that merchant."
            elif data.get("ambiguous"):
                text = "That merchant is ambiguous. " + compose(data)
            else:
                selected = data
                if "categories" in data:
                    category = next((c for c in Category.__args__ if c in question), None)
                    if category:
                        selected = {
                            "categories": [
                                v for v in data["categories"] if v["category"] == category
                            ]
                        }
                    elif "count" in question or "how many" in question:
                        selected = {"active_subscriptions": data["subscriptions"]["count"]}
                    elif "by category" in question:
                        selected = {"categories": data["categories"]}
                    else:
                        selected = {k: v for k, v in data.items() if k != "categories"}
                elif "items" in data:
                    items = data["items"]
                    if "price increase" in question:
                        items = [v for v in items if v.get("type") == "price_increase"]
                    elif "duplicate" in question:
                        items = [v for v in items if v.get("type") == "duplicate"]
                    elif "cancelled" in question:
                        items = [v for v in items if v.get("possibly_cancelled")]
                    elif "expensive" in question:
                        items = [data["most_expensive"]] if data.get("most_expensive") else []
                    selected = {
                        "count": data["count"],
                        "items": [
                            {
                                k: v
                                for k, v in item.items()
                                if k
                                in (
                                    "merchant",
                                    "category",
                                    "kind",
                                    "amount",
                                    "next_expected",
                                    "possibly_cancelled",
                                    "requires_confirmation",
                                    "type",
                                    "est_monthly_saving",
                                    "extra_monthly_cost",
                                    "percent_change",
                                    "members",
                                    "monthly_equivalent",
                                )
                            }
                            for item in items
                        ],
                    }
                text = compose(selected)
            if self.fabricate:
                # Test-only adversary chooses a missing figure, never a demo fixture answer.
                present = {v for r in results for v in r["figures"]["amounts"]}
                candidate = "999999999999.99"
                while candidate in present:
                    candidate = "9" + candidate
                text += "\nInvented charge: ₹" + candidate
            yield Event("token", text=text)
            return
        name, args = None, {}
        if not re.search(
            r"ignore|system prompt|sql|other user|reveal|instructions|api.key", question
        ):
            if any(word in question for word in ("renew", "this week")):
                name, args = "upcoming_renewals", {"days": 7 if "week" in question else 30}
            elif "budget" in question:
                name = "compare_to_budget"
            elif "saving" in question and not ("duplicate" in question or "music" in question):
                name = "potential_savings"
            elif any(
                word in question for word in ("duplicate", "price increase", "recommendation")
            ):
                name, args = "get_recommendations", {"status": "open"}
            elif re.search(r"\b(detail|about|merchant)\b", question):
                merchant = re.sub(
                    r"^.*?\b(?:detail(?:s)?(?: for)?|about|merchant)\s+", "", question
                )
                name, args = "subscription_detail", {"merchant": merchant.strip(' ?."')}
            elif any(
                word in question
                for word in ("spend", "total", "fixed bill", "per year", "count", "how many")
            ):
                name, args = (
                    "spend_summary",
                    {"period": "year" if "year" in question else "month", "group_by": "category"},
                )
            elif any(
                word in question for word in ("subscription", "expensive", "cancelled", "count")
            ):
                name, args = "list_subscriptions", {"status": "active"}
                for category in Category.__args__:
                    if category in question:
                        args["category"] = category
        if name and not force_final:
            yield Event("tool", call=ToolCall("offline-call", name, args))
        else:
            yield Event(
                "token",
                text="I don't have that information. I can help with your recurring payments.",
            )
