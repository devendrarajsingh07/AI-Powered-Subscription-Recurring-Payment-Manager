"""Local positioned-text/OCR extraction. No DB, LLM, network or application credentials.

Run only through the bounded subprocess controller. Every row requires user review. Numerical
validation delegates to ingestion; reconciliation uses Decimal, never float money.
"""

import csv
import io
import re
import signal
import subprocess
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.ingestion import _money, parse_csv

DATE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2} [A-Za-z]{3} \d{4})(?=\s|$)"
)
GUIDANCE = (
    "No readable transaction table found. Use an English text PDF or a clean, straight scan "
    "around 200 dpi or better; export CSV for photos, handwriting or blurred input."
)


class ExtractionError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def check_ocr_quality(rows):
    if not rows:
        raise ExtractionError("unreadable", GUIDANCE)
    valid = sum(row["date"] is not None and row["amount"] is not None for row in rows)
    confidences = sorted(Decimal(row["confidence"]) for row in rows)
    if valid * 5 < len(rows) * 4 or confidences[len(confidences) // 2] < 40:
        raise ExtractionError("low_quality", GUIDANCE)


def sniff(data, filename):
    extension = Path(filename.lower()).suffix
    kind = (
        "pdf"
        if data.startswith(b"%PDF-")
        else "png"
        if data.startswith(b"\x89PNG\r\n\x1a\n")
        else "jpeg"
        if data.startswith(b"\xff\xd8\xff")
        else None
    )
    allowed = {"pdf": {".pdf"}, "png": {".png"}, "jpeg": {".jpg", ".jpeg"}}
    if kind is None or extension not in allowed[kind]:
        raise ExtractionError(
            "unsupported_file",
            "File signature and extension must match PDF, JPEG or PNG. "
            "Excel is unsupported; export CSV instead.",
        )
    # An appended ZIP/HTML after the format terminator is not accepted.
    if kind == "pdf" and not data.rstrip().endswith(b"%%EOF"):
        raise ExtractionError(
            "invalid_file", "PDF is incomplete or contains trailing data; export a fresh PDF."
        )
    if kind == "jpeg" and not data.endswith(b"\xff\xd9"):
        raise ExtractionError("invalid_file", "JPEG is incomplete or contains trailing data.")
    if kind == "png" and not data.endswith(b"IEND\xaeB`\x82"):
        raise ExtractionError("invalid_file", "PNG is incomplete or contains trailing data.")
    return kind


def virtual_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["date", "description", "amount", "type"])
    for row in rows:
        writer.writerow(
            [
                row.get("date") or "",
                row.get("description") or "",
                row.get("amount") or "",
                row.get("type") or "",
            ]
        )
    return output.getvalue().encode("utf-8")


def validate_row(row):
    result = parse_csv(virtual_csv([row]))
    if len(result.transactions) != 1 or result.errors:
        return None
    return result.transactions[0]


@contextmanager
def page_deadline(seconds):
    def timed_out(signum, frame):
        raise ExtractionError(
            "page_timeout",
            "A page exceeded its extraction time limit; split the statement or use CSV.",
        )

    old = signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def timed_pages(source, count, seconds):
    from pdfminer.high_level import extract_pages

    pages = iter(extract_pages(str(source)))
    for number in range(1, count + 1):
        with page_deadline(seconds):
            yield number, next(pages)


def grouped(words):
    lines = []
    for word in sorted(words, key=lambda w: (w["y"], w["x"])):
        if not lines or abs(word["y"] - lines[-1][0]["y"]) > max(3, word["height"] / 3):
            lines.append([word])
        else:
            lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x"]) for line in lines]


def text_words(page):
    from pdfminer.layout import LTChar, LTTextLine

    words = []

    def visit(item):
        if isinstance(item, LTTextLine):
            letters = []

            def flush():
                if letters:
                    words.append(
                        dict(
                            text="".join(c.get_text() for c in letters),
                            x=letters[0].x0,
                            y=page.height - letters[0].y1,
                            height=letters[0].height,
                            confidence="100",
                        )
                    )
                    letters.clear()

            for char in item:
                if isinstance(char, LTChar) and not char.get_text().isspace():
                    letters.append(char)
                else:
                    flush()
            flush()
        elif hasattr(item, "__iter__"):
            for child in item:
                visit(child)

    visit(page)
    return words


def normalize_image(image):
    from PIL import Image, ImageFilter, ImageOps

    image = ImageOps.exif_transpose(image).convert("L")
    if image.width < 3000 and image.width * image.height * 4 <= 25_000_000:
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    image = ImageOps.autocontrast(image).filter(ImageFilter.MedianFilter(3))
    # Projection scoring on a small copy avoids a computer-vision dependency. Small skew only.
    sample = image.copy()
    sample.thumbnail((800, 1200))
    best_angle, best_score, baseline = 0, -1, 0
    for step in range(-4, 5):
        angle = step / 2
        rotated = sample.rotate(angle, fillcolor=255)
        projection = rotated.reduce((rotated.width, 1))
        score = sum((255 - value) ** 2 for value in projection.get_flattened_data())
        if angle == 0:
            baseline = score
        if score > best_score:
            best_angle, best_score = angle, score
    if best_angle and best_score > baseline * 1.05:
        image = image.rotate(best_angle, expand=True, fillcolor=255)
    # New image/PNG never carries EXIF or source metadata.
    image.info.clear()
    return image


def ocr_words(image, directory, page_seconds):
    path = Path(directory) / "normalized.png"
    normalized = normalize_image(image)
    normalized.save(path, format="PNG")
    process = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "eng", "--psm", "6", "tsv"],
        capture_output=True,
        timeout=page_seconds,
        check=False,
    )
    if process.returncode:
        raise ExtractionError("ocr_failed", GUIDANCE)
    words = []
    for row in csv.DictReader(
        io.StringIO(process.stdout.decode("utf-8", errors="replace")), delimiter="\t"
    ):
        if row.get("text", "").strip() and Decimal(row["conf"]) >= 0:
            words.append(
                dict(
                    text=row["text"].strip(),
                    x=int(row["left"]),
                    y=int(row["top"]),
                    height=int(row["height"]),
                    confidence=row["conf"],
                )
            )
    return words


def header(line):
    names = {
        "date": "date",
        "description": "description",
        "narration": "description",
        "particulars": "description",
        "amount": "amount",
        "type": "type",
        "withdrawal": "debit",
        "debit": "debit",
        "deposit": "credit",
        "credit": "credit",
        "balance": "balance",
    }
    columns = {}
    for word in line:
        key = re.sub(r"[^a-z]", "", word["text"].lower())
        if key in names and names[key] not in columns:
            columns[names[key]] = word["x"]
    if {"date", "description"} <= columns.keys() and (
        {"amount", "debit", "credit"} & columns.keys()
    ):
        return columns
    return None


def money_text(value):
    try:
        match = re.search(r"\s*(Dr|Cr)\s*$", value, re.I)
        amount = _money(value[: match.start()] if match else value)
        if match and match.group(1).lower() == "dr":
            amount = -abs(amount)
        return str(amount.quantize(Decimal(".01")))
    except (InvalidOperation, ValueError):
        return None


def reconstruct(words, page, *, ocr=False):
    rows, metadata, columns = [], {}, None
    for line in grouped(words):
        text = " ".join(word["text"] for word in line)
        for label, key in (
            ("Opening Balance", "opening"),
            ("Closing Balance", "closing"),
            ("Total Debit", "total_debit"),
            ("Total Credit", "total_credit"),
        ):
            match = re.search(re.escape(label) + r"\s*[:=]?\s*(.+)$", text, re.I)
            if match:
                metadata[key] = money_text(match.group(1))
        found = header(line)
        if found:
            columns = found
            continue
        match = DATE.match(text)
        candidate_date = ""
        if (
            not match
            and columns
            and not re.match(r"(?i)^(page\b|opening\b|closing\b|total\b|synthetic\b)", text)
        ):
            candidate_date = " ".join(
                word["text"] for word in line if word["x"] < columns["description"] - 5
            )
            money_start = min(
                (x for key, x in columns.items() if key in ("debit", "credit", "amount")),
                default=10**8,
            )
            if not any(
                word["x"] >= money_start - 5 and re.search(r"\d", word["text"]) for word in line
            ):
                candidate_date = ""
        if not match and not candidate_date:
            if (
                rows
                and columns
                and not re.match(r"(?i)^(page\b|opening\b|closing\b|total\b|synthetic\b)", text)
            ):
                start = columns["description"]
                end = min(
                    (
                        x
                        for key, x in columns.items()
                        if key not in ("date", "description") and x > start
                    ),
                    default=10**8,
                )
                if line[0]["x"] >= start - 5 and line[-1]["x"] < end - 5:
                    rows[-1]["description"] = (rows[-1]["description"] + " " + text)[:1000]
            continue
        fields, field_scores = {}, {}
        confidence = min(Decimal(word["confidence"]) for word in line)
        flags = ["Review extracted row"]
        if columns:
            ordered = sorted(columns, key=columns.get)
            # Headers align with the beginning of each column; retain every word in its region.
            for word in line:
                candidates = [name for name in ordered if word["x"] >= columns[name] - 5]
                key = candidates[-1] if candidates else "date"
                fields[key] = (fields.get(key, "") + " " + word["text"]).strip()
                field_scores.setdefault(key, []).append(Decimal(word["confidence"]))
            # Written month dates may cross a narrow Date heading; explicit leading date wins.
            fields["date"] = match.group() if match else candidate_date
        else:
            suffix = re.search(r"([\d,]+\.\d{2})\s*(Dr|Cr|debit|credit)\s*$", text, re.I)
            fields = {
                "date": match.group(),
                "description": text[match.end() : suffix.start()].strip() if suffix else "",
                "amount": suffix.group(1) if suffix else "",
                "type": suffix.group(2) if suffix else "",
            }
            flags.append("Line layout: check column assignments")
        if "debit" in fields or "credit" in fields:
            try:
                debit, credit = _money(fields.get("debit", "0")), _money(fields.get("credit", "0"))
                if (debit > 0) == (credit > 0) or debit < 0 or credit < 0:
                    raise ValueError
                fields["amount"], fields["type"] = (
                    (str(debit), "debit") if debit > 0 else (str(credit), "credit")
                )
                field_scores["amount"] = field_scores.get(fields["type"], [])
                field_scores["type"] = field_scores["amount"]
            except (ValueError, InvalidOperation):
                fields["amount"], fields["type"] = "", ""
        suffix = re.search(r"\s*(Dr|Cr)\s*$", fields.get("amount", ""), re.I)
        if suffix:
            fields["type"] = suffix.group(1)
            fields["amount"] = fields["amount"][: suffix.start()].strip()
            field_scores["type"] = field_scores.get("amount", [])
        transaction = validate_row(fields)
        row = dict(
            date=transaction.date.isoformat() if transaction else None,
            description=fields.get("description", "")[:1000],
            amount=str(transaction.amount) if transaction else None,
            type=transaction.type if transaction else None,
            page=page,
            confidence=str(confidence.quantize(Decimal(".01"))),
            flags=flags,
            field_confidence={
                key: str(min(field_scores[key]).quantize(Decimal(".01")))
                if field_scores.get(key)
                else "0.00"
                for key in ("date", "description", "amount", "type")
            },
            balance=money_text(fields["balance"]) if fields.get("balance") else None,
        )
        if not transaction:
            flags.append("Invalid date, amount or type: correct before import")
        if len(fields.get("description", "")) > 1000:
            flags.append("Description exceeded length limit; review truncation")
        if ocr:
            flags.append("OCR: unverified digits require explicit review")
            if confidence < 90:
                flags.append("Low OCR field confidence")
            if re.search(r"[017856]", fields.get("amount", "")):
                flags.append("Check digit shapes and separators")
        rows.append(row)
        if len(rows) > 5000:
            raise ExtractionError(
                "too_many_rows",
                "Statement exceeds the 5,000 extracted-row limit; split it or export CSV.",
            )
    return rows, metadata


def reconcile(rows, metadata):
    previous = Decimal(metadata["opening"]) if metadata.get("opening") is not None else None
    checked, broken = 0, set()
    debit = credit = Decimal("0")
    complete = True
    for index, row in enumerate(rows):
        valid = row.get("amount") is not None and row.get("type") in ("debit", "credit")
        if not valid:
            complete = False
        else:
            amount = Decimal(row["amount"])
            if row["type"] == "debit":
                debit += amount
            else:
                credit += amount
            if previous is not None and row.get("balance") is not None:
                checked += 1
                expected = previous + (amount if row["type"] == "credit" else -amount)
                if expected != Decimal(row["balance"]):
                    broken.update(i for i in (index - 1, index, index + 1) if 0 <= i < len(rows))
        previous = Decimal(row["balance"]) if row.get("balance") is not None else None
    totals_checked = 0
    if complete:
        for key, actual in (("total_debit", debit), ("total_credit", credit)):
            if metadata.get(key) is not None:
                totals_checked += 1
                if actual != Decimal(metadata[key]):
                    broken.update(range(len(rows)))
        if metadata.get("opening") is not None and metadata.get("closing") is not None:
            totals_checked += 1
            if Decimal(metadata["opening"]) + credit - debit != Decimal(metadata["closing"]):
                broken.update(range(len(rows)))
    for index in broken:
        if "Balance/totals mismatch or adjacent break" not in rows[index]["flags"]:
            rows[index]["flags"].append("Balance/totals mismatch or adjacent break")
    status = (
        "mismatch"
        if broken
        else "matched"
        if complete and (checked == len(rows) or totals_checked)
        else "unavailable"
    )
    return dict(
        status=status,
        balance_checks=checked,
        total_checks=totals_checked,
        opening=metadata.get("opening"),
        closing=metadata.get("closing"),
    )


def clean_pdf(data, password, limits):
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        if not password:
            raise ExtractionError(
                "password_required",
                "This PDF is encrypted. Enter its password in the password field and retry.",
            )
        if not reader.decrypt(password):
            raise ExtractionError(
                "wrong_password", "PDF password was not accepted; check it and retry."
            )
    page_count = len(reader.pages)
    if not 1 <= page_count <= limits["pages"]:
        raise ExtractionError(
            "too_many_pages",
            "PDF exceeds the configured page limit (maximum 30); split it before upload.",
        )
    # Copy pages only: omit document scripts, actions and embedded-file catalog entries.
    writer = PdfWriter()
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (
            width <= 0
            or height <= 0
            or width * height * (200 / 72) ** 2 > limits["megapixels"] * 1_000_000
        ):
            raise ExtractionError("image_too_large", "A PDF page exceeds the render pixel limit.")
        writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), page_count


def extract(data, filename, password, directory, limits, progress=lambda *args: None):
    from PIL import Image

    kind = sniff(data, filename)
    Image.MAX_IMAGE_PIXELS = limits["megapixels"] * 1_000_000
    rows, metadata, any_ocr = [], {}, False
    if kind == "pdf":
        cleaned, page_count = clean_pdf(data, password, limits)
        source = Path(directory) / "statement.pdf"
        source.write_bytes(cleaned)
        progress(0, page_count)
        for number, page in timed_pages(source, page_count, limits["page_seconds"]):
            words = text_words(page)
            page_rows, page_meta = reconstruct(words, number)
            if not page_rows:
                any_ocr = True
                target = Path(directory) / "render"
                result = subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(number),
                        "-l",
                        str(number),
                        "-singlefile",
                        "-r",
                        "200",
                        "-gray",
                        "-png",
                        str(source),
                        str(target),
                    ],
                    capture_output=True,
                    timeout=limits["page_seconds"],
                    check=False,
                )
                if result.returncode:
                    raise ExtractionError("render_failed", GUIDANCE)
                with Image.open(str(target) + ".png") as image:
                    page_rows, page_meta = reconstruct(
                        ocr_words(image, directory, limits["page_seconds"]), number, ocr=True
                    )
                check_ocr_quality(page_rows)
            rows.extend(page_rows)
            metadata.update(page_meta)
            progress(number, page_count)
        source_type = "pdf_ocr" if any_ocr else "pdf_text"
    else:
        page_count, source_type = 1, "image_ocr"
        progress(0, 1)
        try:
            with page_deadline(limits["page_seconds"]):
                with Image.open(io.BytesIO(data)) as image:
                    if image.width * image.height > limits["megapixels"] * 1_000_000:
                        raise Image.DecompressionBombError()
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    rows, metadata = reconstruct(
                        ocr_words(image, directory, limits["page_seconds"]), 1, ocr=True
                    )
        except Image.DecompressionBombError:
            raise ExtractionError(
                "image_too_large",
                "Image exceeds the 25-megapixel limit; resize it or export PDF/CSV.",
            ) from None
        progress(1, 1)
    if not rows:
        raise ExtractionError("unreadable", GUIDANCE)
    if source_type != "pdf_text":
        check_ocr_quality(rows)
    if len(rows) > 5000:
        raise ExtractionError(
            "too_many_rows", "Split statements with more than 5,000 extracted rows."
        )
    for index, row in enumerate(rows):
        row["index"] = index
    reconciliation = reconcile(rows, metadata)
    return dict(
        rows=rows,
        source_type=source_type,
        page_count=page_count,
        flagged_count=sum(bool(row["flags"]) for row in rows),
        reconciliation=reconciliation,
        warnings=[
            "Every extracted row requires your review. OCR can misread digits; "
            "balanced totals do not prove each field correct."
        ],
    )
