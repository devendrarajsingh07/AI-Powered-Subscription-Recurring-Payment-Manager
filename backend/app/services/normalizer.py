"""Merchant normalization and safe display of untrusted bank descriptions."""

import re
import unicodedata

NOISE = frozenset(
    "upi pos neft imps ach nach ecs bill billing com inc ltd pvt private limited "
    "payment payments paid debit credit dr cr purchase transfer txn transaction ref reference "
    "mandate autopay auto pay recurring india in www http https card visa mastercard "
    "hdfc icici sbi axis ybl okhdfcbank okicici oksbi paytm phonepe razorpay "
    "bangalore bengaluru mumbai delhi chennai hyderabad pune kolkata gurgaon gurugram "
    "noida internet bank banking vpa collect to on via at rs inr".split()
)

# Longest aliases first. Apple products intentionally retain one merchant identity;
# the detector separates overlapping products by amount and billing schedule.
ALIASES = {
    "google youtube premium": "youtube premium",
    "youtube premium": "youtube premium",
    "google youtube": "youtube premium",
    "youtube": "youtube premium",
    "netflix entertainment": "netflix",
    "netflix": "netflix",
    "spotify": "spotify",
    "amazon prime video": "amazon prime",
    "amazon prime": "amazon prime",
    "apple icloud": "apple",
    "apple music": "apple",
    "apple": "apple",
    "google one": "google one",
    "google storage": "google one",
    "microsoft office": "microsoft",
    "microsoft": "microsoft",
    "notion software": "notion",
    "notion": "notion",
    "github": "github",
    "dropbox": "dropbox",
    "adobe creative cloud": "adobe",
    "adobe": "adobe",
    "cult fit": "cultfit",
    "cultfit": "cultfit",
    "airtel": "airtel",
    "jio": "jio",
    "disney hotstar": "hotstar",
    "hotstar": "hotstar",
    "zomato": "zomato",
    "swiggy": "swiggy",
    "uber": "uber",
    "ola": "ola",
}
_SORTED_ALIASES = sorted(ALIASES, key=len, reverse=True)


def safe_display(value: str) -> str:
    """For echoed CSV fields only. Never overwrite the stored raw description."""
    value = "".join(ch if ch.isprintable() else " " for ch in value)
    return value.lstrip(" \t\r\n=+-@")


def normalize_merchant(description: str) -> str:
    text = unicodedata.normalize("NFKC", description).lower()
    # Remove whole alphanumeric reference tokens before stripping standalone digits.
    text = re.sub(r"\b[a-z]*\d+[a-z\d]*\b", " ", text)
    tokens = re.findall(r"[a-z]+", text)
    meaningful = [token for token in tokens if token not in NOISE]
    cleaned = " ".join(meaningful)
    for alias in _SORTED_ALIASES:
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", cleaned):
            return ALIASES[alias]
    return " ".join(meaningful[:2]) or "unknown"
