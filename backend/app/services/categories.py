"""Rule-based labels. Unknowns stay unconfirmed until the later LLM/user workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    name: str
    kind: str = "subscription"
    requires_confirmation: bool = False


MERCHANT_CATEGORIES = {
    "netflix": "streaming",
    "youtube premium": "streaming",
    "amazon prime": "streaming",
    "hotstar": "streaming",
    "spotify": "music",
    "google one": "cloud",
    "dropbox": "cloud",
    "cultfit": "fitness",
    "gym": "fitness",
    "airtel": "telecom",
    "jio": "telecom",
    "adobe": "software",
    "microsoft": "software",
    "github": "software",
    "notion": "software",
    "newspaper": "news",
    "news": "news",
}
FIXED_CATEGORIES = {
    "rent": "rent",
    "landlord": "rent",
    "emi": "loan",
    "loan": "loan",
    "insurance": "insurance",
    "lic": "insurance",
    "electricity": "utilities",
    "water": "utilities",
    "utility": "utilities",
    "utilities": "utilities",
    "broadband": "utilities",
    "gas": "utilities",
}


def categorize(merchant: str, descriptions: tuple[str, ...] = ()) -> Category:
    words = set(merchant.split())
    for word, category in FIXED_CATEGORIES.items():
        if word in words:
            return Category(category, kind="fixed_bill")
    if merchant == "apple":
        # Only explicit product names are evidence; generic Apple billing is ambiguous.
        lowered = [description.lower() for description in descriptions]
        cloud = sum("icloud" in text for text in lowered)
        music = sum("music" in text for text in lowered)
        if cloud > music:
            return Category("cloud")
        if music > cloud:
            return Category("music")
        return Category("unknown", requires_confirmation=True)
    category = MERCHANT_CATEGORIES.get(merchant)
    if category is None:
        category = next(
            (MERCHANT_CATEGORIES[w] for w in merchant.split() if w in MERCHANT_CATEGORIES), None
        )
    return Category(category) if category else Category("unknown", requires_confirmation=True)
