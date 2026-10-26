"""Bounded, offline MIME receipt parsing. No mailbox, network, LLM or original-body storage."""

import re
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

from app.services.ingestion import _date as parse_date
from app.services.ingestion import _money as parse_money
from app.services.normalizer import normalize_merchant, safe_display

MAX_BYTES = 1024 * 1024
MAX_PARTS = 32
MAX_TEXT = 64 * 1024


class ReceiptError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class _Text(HTMLParser):
    """Render text only: never execute HTML or fetch links, images or attachments."""

    blocked = {"script", "style", "head", "iframe", "object", "svg", "blockquote"}
    blocks = {"p", "div", "br", "tr", "li", "table", "h1", "h2"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.pieces = []

    def handle_starttag(self, tag, attrs):
        if tag in self.blocked:
            self.hidden.append(tag)
        if not self.hidden and tag in self.blocks:
            self.pieces.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if not self.hidden and tag in self.blocks:
            self.pieces.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.pieces.append(data)


def _body(data):
    if not data:
        raise ReceiptError("empty_receipt", "Choose a non-empty synthetic EML receipt")
    if len(data) > MAX_BYTES:
        raise ReceiptError("receipt_too_large", "EML receipt exceeds the 1 MB limit")
    lowered = data.lower().replace(b"\r\n", b"\n")
    headers, separator, _ = lowered.partition(b"\n\n")
    if not separator or len(headers) > 16 * 1024:
        raise ReceiptError("invalid_receipt", "EML headers are missing or exceed the limit")
    if lowered.count(b"\ncontent-type:") >= MAX_PARTS:
        raise ReceiptError("receipt_too_complex", "EML has too many MIME parts")
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
        plain, html, pending, count = [], [], [(message, 0)], 0
        while pending:
            part, depth = pending.pop()
            count += 1
            if count > MAX_PARTS or depth > 5:
                raise ReceiptError("receipt_too_complex", "EML MIME nesting exceeds the limit")
            if part.defects:
                raise ReceiptError("invalid_receipt", "EML MIME structure is malformed")
            if part.get_filename() or part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "message/rfc822":
                continue  # Forwarded/attached messages are not evidence of a new charge.
            if part.is_multipart():
                pending.extend((child, depth + 1) for child in part.iter_parts())
            elif part.get_content_type() in ("text/plain", "text/html"):
                text = part.get_content()
                if len(text) > MAX_TEXT:
                    raise ReceiptError("receipt_text_too_large", "Receipt text exceeds 64 KB")
                (plain if part.get_content_type() == "text/plain" else html).append(text)
        selected = plain or html
        if len(selected) != 1:
            raise ReceiptError("ambiguous_receipt", "EML needs one supported message body")
        text = selected[0]
        if not plain:
            parser = _Text()
            parser.feed(text)
            text = "".join(parser.pieces)
        # Quoted replies must not turn a past payment into a new candidate.
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    except ReceiptError:
        raise
    except (ValueError, TypeError, LookupError, RecursionError, UnicodeError):
        raise ReceiptError("invalid_receipt", "EML content cannot be safely decoded") from None


def _values(text, labels):
    return set(
        value.strip()
        # Horizontal whitespace only: do not rescan runs of blank lines quadratically
        # or borrow a value from the next labelled line.
        for value in re.findall(r"(?im)^[ \t]*(?:" + labels + r")[ \t]*:[ \t]*([^\r\n]+)", text)
    )


def parse_receipt(data: bytes):
    """Return one unverified candidate; absent/ambiguous fields remain absent, never guessed."""
    text = _body(data)
    status = {value.lower() for value in _values(text, "payment status")}
    if status not in ({"paid"}, {"successful"}, {"succeeded"}):
        raise ReceiptError(
            "not_paid_receipt", "Only explicitly paid receipts are supported; no charge imported"
        )
    if _values(text, "refund status|amount refunded"):
        raise ReceiptError("not_paid_receipt", "Refund messages are not imported as paid charges")
    currencies = {value.upper() for value in _values(text, "currency")}
    if currencies - {"INR"}:
        raise ReceiptError("unsupported_currency", "Only INR receipts are supported")
    flags = ["email_review_required", "email_authenticity_unverified", "not_bank_reconciled"]
    row = dict(
        index=0,
        date=None,
        description="",
        amount=None,
        type="debit",
        page=1,
        confidence="0.00",
        field_confidence={},
        flags=flags,
        balance=None,
    )
    merchants = _values(text, "merchant|service")
    if len(merchants) == 1:
        merchant = next(iter(merchants))
        if len(merchant) <= 100 and re.fullmatch(r"[\w &().+\-]+", merchant):
            row["description"] = safe_display(normalize_merchant(merchant))
    if not row["description"]:
        flags.append("missing_or_ambiguous_merchant")
    dates = _values(text, "payment date|charged on|paid on|transaction date")
    if len(dates) == 1:
        try:
            row["date"] = parse_date(next(iter(dates))).isoformat()
        except ValueError:
            pass
    if row["date"] is None:
        flags.append("missing_or_ambiguous_payment_date")
    amounts = _values(text, "amount paid|total paid|amount charged")
    if len(amounts) == 1:
        amount = next(iter(amounts))
        if re.search(r"(?i)\b(?:USD|EUR|GBP)\b|[$\u20ac\u00a3]", amount):
            raise ReceiptError("unsupported_currency", "Only INR receipts are supported")
        match = re.fullmatch(
            r"(?i)(?P<prefix>INR|Rs\.?|\u20b9)?\s*"
            r"(?P<number>(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})"
            r"(?:\.\d{1,2})?)\s*(?P<suffix>INR)?",
            amount,
        )
        if match and (currencies or match["prefix"] or match["suffix"]):
            try:
                value = parse_money(match["number"])
                if Decimal("0") < value <= Decimal("9999999999.99"):
                    row["amount"] = format(value, ".2f")
            except ValueError:
                pass
    if row["amount"] is None:
        flags.append("missing_or_ambiguous_paid_amount_or_currency")
    return dict(
        source_type="email_receipt",
        page_count=1,
        rows=[row],
        flagged_count=1,
        reconciliation=dict(
            status="unavailable", balance_checks=0, total_checks=0, opening=None, closing=None
        ),
        warnings=[
            "Review every field. Email receipts do not prove settlement or authenticity.",
            "Attachments, quoted messages, HTML active content and remote resources are ignored.",
            "Header dates and renewal amounts are not payment evidence. No bank reconciliation.",
        ],
    )
