"""Bounded, pure CSV parsing used by detector evaluation and later upload endpoints.

Database persistence, background progress, and cross-upload idempotency belong to Phase 3.
Raw descriptions remain unchanged; every preview field is sanitized for display.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Mapping

from app.services.detector import Transaction
from app.services.normalizer import safe_display

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y")
HEADER_ALIASES = {
    "date": ("date", "transaction date", "txn date", "trans date", "value date"),
    "description": ("description", "narration", "transaction remarks", "particulars", "remarks"),
    "amount": ("amount", "transaction amount"),
    "type": ("type", "transaction type", "dr cr", "debit credit"),
    "debit": ("debit", "debit amount", "withdrawal", "withdrawal amt", "withdrawal amount"),
    "credit": ("credit", "credit amount", "deposit", "deposit amt", "deposit amount"),
    "currency": ("currency",),
}


class CsvValidationError(ValueError):
    """File or mapping is unusable; individual bad rows use RowError instead."""


@dataclass(frozen=True)
class RowError:
    line: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    transactions: tuple[Transaction, ...]
    row_count: int
    errors: tuple[RowError, ...]
    mapping: dict[str, str]

    @property
    def skipped_count(self) -> int:
        return len(self.errors)


def _header(value: str) -> str:
    return re.sub(r"[^a-z]+", " ", value.lower()).strip()


def _reader(data: bytes):
    if len(data) > MAX_BYTES:
        raise CsvValidationError("CSV exceeds the 5 MB limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV must be UTF-8 encoded") from exc
    if not text.strip():
        raise CsvValidationError("CSV is empty")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        # Headers provide a reliable fallback when malformed rows confuse Sniffer.
        first_line = text.splitlines()[0]
        delimiter = max(",;\t|", key=first_line.count)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        headers = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise CsvValidationError("CSV header is malformed") from exc
    if (
        not headers
        or any(not header.strip() for header in headers)
        or len(set(headers)) != len(headers)
    ):
        raise CsvValidationError("CSV headers must be unique and nonempty")
    return headers, reader


def suggest_mapping(headers: list[str]) -> dict[str, str]:
    normalized = {_header(header): header for header in headers}
    return {
        field: next(normalized[alias] for alias in aliases if alias in normalized)
        for field, aliases in HEADER_ALIASES.items()
        if any(alias in normalized for alias in aliases)
    }


def preview_csv(data: bytes, *, limit: int = 5) -> dict:
    if not 1 <= limit <= 20:
        raise CsvValidationError("Preview limit must be between 1 and 20")
    headers, reader = _reader(data)
    rows = []
    row_count = 0
    malformed = False
    try:
        for row in reader:
            if not any(field.strip() for field in row):
                continue
            row_count += 1
            if row_count > MAX_ROWS:
                raise CsvValidationError("CSV exceeds the 50,000 row limit")
            if len(rows) < limit:
                rows.append([safe_display(field) for field in row])
    except csv.Error:
        malformed = True
    return {
        "columns": [safe_display(h) for h in headers],
        "suggested_mapping": suggest_mapping(headers),
        "rows": rows,
        "row_count": row_count,
        "malformed_csv": malformed,
    }


def _money(value: str) -> Decimal:
    cleaned = re.sub(r"(?i)\b(?:INR|RS)\.?", "", value).replace("₹", "").replace(",", "").strip()
    if cleaned in ("-", "--", "—"):
        cleaned = "0"
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    amount = Decimal(cleaned or "0")
    if not amount.is_finite():
        raise ValueError("Nonfinite amount")
    return amount


def _date(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError("Unsupported date")


def parse_csv(data: bytes, mapping: Mapping[str, str] | None = None) -> ParseResult:
    headers, reader = _reader(data)
    selected = dict(mapping) if mapping is not None else suggest_mapping(headers)
    if set(selected) - set(HEADER_ALIASES) or any(
        value not in headers for value in selected.values()
    ):
        raise CsvValidationError("Mapping refers to an unknown field or column")
    if len(set(selected.values())) != len(selected):
        raise CsvValidationError("Each mapped field must use a different column")
    separate = "debit" in selected or "credit" in selected
    if not {"date", "description"} <= selected.keys():
        raise CsvValidationError("Map date and description columns")
    if not separate and not {"amount", "type"} <= selected.keys():
        raise CsvValidationError("Map amount and type, or separate debit/credit columns")
    if separate and ("amount" in selected or "type" in selected):
        raise CsvValidationError("Choose either amount/type or separate debit/credit columns")
    transactions, errors = [], []
    count = 0
    try:
        for row in reader:
            if not any(field.strip() for field in row):
                continue
            count += 1
            if count > MAX_ROWS:
                raise CsvValidationError("CSV exceeds the 50,000 row limit")
            line = reader.line_num
            if len(row) != len(headers):
                errors.append(RowError(line, "Column count does not match header"))
                continue
            fields = dict(zip(headers, row))
            values = {key: fields[column] for key, column in selected.items()}
            try:
                charged_on = _date(values["date"])
            except ValueError:
                errors.append(RowError(line, "Invalid date"))
                continue
            if not values["description"].strip():
                errors.append(RowError(line, "Missing description"))
                continue
            try:
                if separate:
                    debit = _money(values.get("debit", "0"))
                    credit = _money(values.get("credit", "0"))
                    if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
                        raise ValueError("Ambiguous debit/credit")
                    direction, amount = ("debit", debit) if debit > 0 else ("credit", credit)
                else:
                    direction = values["type"].strip().lower()
                    direction = {"dr": "debit", "cr": "credit"}.get(direction, direction)
                    amount = abs(_money(values["amount"]))
                currency = values.get("currency", "INR").strip().upper()
                if not re.fullmatch("[A-Z]{3}", currency):
                    raise ValueError("Invalid currency")
                tx = Transaction(
                    charged_on, values["description"], amount, direction, currency, id=line
                )
            except (ValueError, DecimalException):
                errors.append(
                    RowError(line, "Invalid amount, type, currency, or debit/credit pair")
                )
                continue
            transactions.append(tx)
    except csv.Error:
        # The malformed record cannot be safely resynchronized; retain valid preceding rows.
        count += 1
        if count > MAX_ROWS:
            raise CsvValidationError("CSV exceeds the 50,000 row limit") from None
        errors.append(
            RowError(reader.line_num, "Malformed CSV quoting; remaining input unreadable")
        )
    return ParseResult(tuple(transactions), count, tuple(errors), selected)
