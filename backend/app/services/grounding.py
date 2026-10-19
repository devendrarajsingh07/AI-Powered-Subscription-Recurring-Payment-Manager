"""Fail-closed figure provenance. Does not prove prose claims or associations."""

import json
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

MONTHS = (
    "January February March April May June July August September October November December".split()
)
WORDS = dict(
    zip(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty "
        "sixty seventy eighty ninety".split(),
        list(range(20)) + list(range(20, 100, 10)),
    )
)
NUMBER = r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?(?!\w|\.\d)"


def decimal(value):
    return str(Decimal(value.replace(",", "")).normalize())


def extract(answer, merchant_names=()):
    text = unicodedata.normalize("NFKC", answer)
    figures = set()

    def dates(match):
        raw = match.group(0)
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d %Y",
            "%b %d %Y",
        ):
            try:
                value = datetime.strptime(raw.replace(",", ""), fmt).date().isoformat()
                figures.add(("dates", value))
                return " "
            except ValueError:
                pass
        raise ValueError("Unrecognized date")

    month = "(?:" + "|".join(MONTHS + [v[:3] for v in MONTHS]) + ")"
    text = re.sub(
        r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|"
        rf"\d{{1,2}} {month} \d{{4}}|{month} \d{{1,2}},? \d{{4}})\b",
        dates,
        text,
        flags=re.I,
    )

    def number(match, kind):
        figures.add((kind, decimal(re.search(NUMBER, match.group(0)).group(0))))
        return " "

    text = re.sub(
        r"(?:₹|INR\s*|Rs\.?\s*)" + NUMBER, lambda m: number(m, "amounts"), text, flags=re.I
    )
    text = re.sub(
        NUMBER + r"\s*(?:%|percent\b)", lambda m: number(m, "percentages"), text, flags=re.I
    )

    def plain(match):
        return number(match, "amounts" if "." in match.group(0) else "counts")

    text = re.sub(NUMBER, plain, text)
    # Written English counts, including compound hundreds/thousands. Unknown numeric
    # notation is rejected below instead of being silently treated as grounded prose.
    vocabulary = "|".join([*WORDS, "hundred", "thousand", "million", "billion"])
    pattern = rf"\b(?:{vocabulary})(?:(?:[ -]| and )+(?:{vocabulary}))*\b"

    def written(match):
        before, after = text[: match.start()], text[match.end() :]
        is_percentage = re.match(r"[ \t]*(?:%|percent\b|per cent\b)", after, re.I)
        is_amount = re.search(r"(?:₹|INR|Rs\.?)\s*$", before, re.I) or re.match(
            r"[ \t]+rupees\b", after, re.I
        )
        for name in merchant_names:
            quoted = json.dumps(name, ensure_ascii=False)
            for span in re.finditer(re.escape(quoted), text, flags=re.I):
                if (
                    span.start() <= match.start()
                    and match.end() <= span.end()
                    and not is_amount
                    and not is_percentage
                ):
                    return match.group()  # A verbatim quoted proper name is data, not a count.
        total = current = 0
        for word in re.findall(r"[a-z]+", match.group().lower()):
            if word in WORDS:
                current += WORDS[word]
            elif word == "hundred":
                current = (current or 1) * 100
            elif word in ("thousand", "million", "billion"):
                total += (current or 1) * {
                    "thousand": 1000,
                    "million": 1000000,
                    "billion": 1000000000,
                }[word]
                current = 0
        kind = "percentages" if is_percentage else "amounts" if is_amount else "counts"
        figures.add((kind, decimal(str(total + current))))
        return " "

    text = re.sub(pattern, written, text, flags=re.I)
    if any(c.isnumeric() for c in text) or re.search(r"\b(?:half|dozen|lakh|crore)\b", text, re.I):
        raise ValueError("Unsupported numeric notation")
    return figures


def verify(answer, results):
    allowed = set()
    names = set()

    def collect(value):
        if isinstance(value, dict):
            if value.get("untrusted") and "data_text" in value:
                names.add(value["data_text"])
            else:
                for item in value.values():
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for result in results:
        collect(result.get("data", {}))
        for kind, values in result.get("figures", {}).items():
            allowed.update((kind, value if kind == "dates" else decimal(value)) for value in values)
    try:
        if re.search(r"\b(today|tomorrow|yesterday)\b", answer, re.I):
            clocks = {result["as_of"] for result in results}
            if len(clocks) != 1:
                return False
            day = datetime.strptime(next(iter(clocks)), "%Y-%m-%d").date()
            answer = re.sub(
                r"\b(today|tomorrow|yesterday)\b",
                lambda match: (
                    day
                    + timedelta(
                        days={"today": 0, "tomorrow": 1, "yesterday": -1}[match.group().lower()]
                    )
                ).isoformat(),
                answer,
                flags=re.I,
            )
        return extract(answer, names) <= allowed
    except (ValueError, InvalidOperation):
        return False


def render_data(results):
    """Deterministic fallback/Offline renderer. No arithmetic or invented values."""

    def lines(value, key=""):
        if isinstance(value, dict):
            if "data_text" in value:
                return [json.dumps(value["data_text"], ensure_ascii=False)]
            result = []
            for name, item in value.items():
                if item is not None and name not in ("currency", "truncated"):
                    result.extend(f"{name.replace('_', ' ')}: {line}" for line in lines(item, name))
            return result
        if isinstance(value, list):
            return [line for item in value for line in lines(item, key)]
        if type(value) is bool:
            return ["yes" if value else "no"]
        if isinstance(value, str) and re.fullmatch(r"-?\d+\.\d{2}", value):
            return [value + "%" if "percent" in key else "₹" + value]
        return [str(value)]

    if not results:
        return "I don't have that information. I can help with your recurring payments."
    return "\n".join(line for result in results for line in lines(result["data"]))
