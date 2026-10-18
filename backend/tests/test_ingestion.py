from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.detector import detect_recurring
from app.services.ingestion import CsvValidationError, parse_csv, preview_csv

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
@pytest.mark.parametrize("date_text", ["2026-01-31", "31/01/2026", "31-01-2026", "31 Jan 2026"])
def test_dates_and_delimiters(delimiter, date_text):
    data = delimiter.join(["date", "description", "amount", "type"]) + "\n"
    data += delimiter.join([date_text, "NETFLIX.COM", "199.00", "debit"])
    result = parse_csv(data.encode())
    assert result.row_count == 1
    assert not result.errors
    assert result.transactions[0].date == date(2026, 1, 31)
    assert result.transactions[0].amount == Decimal("199.00")


def test_handwritten_withdrawal_deposit_export():
    result = parse_csv((DATA / "handwritten_bank.csv").read_bytes())
    assert result.row_count == 29
    assert result.skipped_count == 3
    assert result.mapping["debit"] == "Withdrawal Amt."
    found = detect_recurring(result.transactions, as_of=date(2026, 5, 1))
    assert {(d.merchant, d.kind) for d in found} == {
        ("netflix", "subscription"),
        ("spotify", "subscription"),
        ("rent", "fixed_bill"),
    }
    assert any(tx.raw_description.startswith("=HYPERLINK") for tx in result.transactions)


def test_handwritten_debit_credit_export_and_amount_clusters():
    result = parse_csv((DATA / "handwritten_products.csv").read_bytes())
    assert not result.errors
    found = detect_recurring(result.transactions, as_of=date(2026, 6, 15))
    assert len(found) == 5
    assert len([d for d in found if d.merchant == "apple"]) == 2
    assert next(d for d in found if d.merchant == "cultfit").possibly_cancelled


def test_mapping_confirmation_can_override_unrecognized_headers():
    data = b"When,What,Value,Direction\n2026-01-01,Netflix,199,debit\n"
    assert preview_csv(data)["suggested_mapping"] == {}
    with pytest.raises(CsvValidationError):
        parse_csv(data)
    result = parse_csv(
        data, {"date": "When", "description": "What", "amount": "Value", "type": "Direction"}
    )
    assert result.transactions[0].amount == Decimal("199")


def test_preview_sanitizes_all_echoed_fields_and_preserves_raw_input():
    data = b"date,description,amount,type\n2026-01-01,=HYPERLINK(untrusted),199,debit\n"
    preview = preview_csv(data)
    assert preview["rows"][0][1] == "HYPERLINK(untrusted)"
    assert parse_csv(data).transactions[0].raw_description == "=HYPERLINK(untrusted)"


def test_multiple_bad_rows_report_reasons_without_echoing_financial_data():
    data = (
        b"date,description,amount,type\n2026-01-01,ok,100,debit\n"
        b"bad,private description,100,debit\n2026-02-01,secret,NaN,debit\n"
        b"2026-03-01,secret,100,unknown\n2026-04-01,short\n"
        b"2026-05-01,,100,debit\n2026-06-01,ok,100,credit\n"
    )
    result = parse_csv(data)
    assert len(result.transactions) == 2
    assert result.skipped_count == 5
    assert "private description" not in str(result.errors)
    assert result.errors[0].line == 3


def test_signed_money_and_credit_type_are_explicit():
    result = parse_csv(
        b'date,description,amount,type\n2026-01-01,A,"-1,299.00",dr\n2026-01-02,B,"(299.00)",cr\n'
    )
    assert [t.amount for t in result.transactions] == [Decimal("1299.00"), Decimal("299.00")]
    assert [t.type for t in result.transactions] == ["debit", "credit"]


@pytest.mark.parametrize("amount", ["1e999999999999999", "1e-999999999999", "Infinity", "1e1000"])
def test_extreme_decimal_input_is_reported_without_crashing(amount):
    data = f"date,description,amount,type\n2026-01-01,Netflix,{amount},debit\n".encode()
    result = parse_csv(data)
    assert not result.transactions
    assert result.skipped_count == 1


def test_dash_placeholders_in_bank_columns():
    result = parse_csv(b"date,description,Debit,Credit\n2026-01-01,Netflix,199,-\n")
    assert not result.errors
    assert result.transactions[0].amount == Decimal("199")


def test_file_limits():
    with pytest.raises(CsvValidationError, match="5 MB"):
        parse_csv(b"x" * (5 * 1024 * 1024 + 1))
    data = b"date,description,amount,type\n" + b"2026-01-01,A,1,debit\n" * 50_001
    with pytest.raises(CsvValidationError, match="50,000"):
        parse_csv(data)
    with pytest.raises(CsvValidationError, match="50,000"):
        preview_csv(data)


@pytest.mark.parametrize("data", [b"", b"\xff", b"date,date\n", b"date,,amount\n"])
def test_invalid_files_rejected(data):
    with pytest.raises(CsvValidationError):
        parse_csv(data)


def test_malformed_quote_keeps_preceding_valid_rows():
    data = (
        b"date,description,amount,type\n2026-01-01,Netflix,199,debit\n"
        b'2026-02-01,"unclosed,199,debit\n'
    )
    result = parse_csv(data)
    assert len(result.transactions) == 1
    assert result.skipped_count == 1
    assert "Malformed CSV" in result.errors[0].reason
