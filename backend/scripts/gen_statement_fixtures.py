"""Synthetic statement corpus, labelled from the committed CSV, never detector output."""

import csv
import io
import json
import random
import subprocess
import tempfile
import textwrap
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageFilter
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "extraction"
PASSWORD = "FixtureOnly42!"  # Public, synthetic PDF fixture only; never an account credential.


def indian(value):
    whole, fraction = format(Decimal(value), ".2f").split(".")
    last = whole[-3:]
    rest = whole[:-3]
    groups = []
    while rest:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    return (",".join(groups + [last])) + "." + fraction


def make_pdf(rows, *, split=False, corrupt=False, list_style=False):
    buffer = io.BytesIO()
    width, height = landscape(A4)
    canvas = Canvas(buffer, pagesize=(width, height), invariant=1)
    balance = Decimal("1000000.00")
    position, page = 0, 0
    while position < len(rows):
        page += 1
        canvas.setFont("SyntheticMono", 10)
        canvas.drawString(
            32, height - 30, "SYNTHETIC INR STATEMENT - educational fixture, no real account"
        )
        canvas.setFont("SyntheticMono", 8)
        if page == 1 and split:
            canvas.drawString(32, height - 50, "Opening Balance: " + indian(balance))
        if not list_style:
            for name, x in (("Date", 32), ("Description", 130)):
                canvas.drawString(x, height - 76, name)
            if split:
                for name, x in (("Withdrawal", 500), ("Deposit", 590), ("Balance", 680)):
                    canvas.drawString(x, height - 76, name)
            else:
                canvas.drawString(530, height - 76, "Amount (Dr/Cr)")
        y = height - 96
        while position < len(rows) and y > 60:
            row = rows[position]
            amount = Decimal(row["amount"])
            printed = amount + Decimal("60") if corrupt and position == 0 else amount
            balance += amount if row["type"] == "credit" else -amount
            suffix = "Cr" if row["type"] == "credit" else "Dr"
            description = row["description"]
            if list_style:
                canvas.drawString(32, y, f"{row['date']} {description} {indian(printed)} {suffix}")
                y -= 17
            else:
                from datetime import date

                date_text = date.fromisoformat(row["date"]).strftime(
                    "%d %b %Y" if split else "%d/%m/%Y"
                )
                canvas.drawString(32, y, date_text)
                wrapped = textwrap.wrap(
                    description, width=45, break_long_words=False, break_on_hyphens=False
                ) or [""]
                for offset, part in enumerate(wrapped):
                    canvas.drawString(130, y - offset * 11, part)
                if split:
                    canvas.drawString(590 if row["type"] == "credit" else 500, y, indian(printed))
                    canvas.drawString(680, y, indian(balance))
                else:
                    canvas.drawString(530, y, indian(printed) + " " + suffix)
                y -= max(17, 11 * len(wrapped) + 5)
            position += 1
        if split and position == len(rows):
            canvas.drawString(32, 37, "Closing Balance: " + indian(balance))
        canvas.drawString(32, 22, f"Page {page} - synthetic test data only")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(
        TTFont("SyntheticMono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    )
    with (ROOT / "data/sample_transactions.csv").open(newline="") as handle:
        rows = sorted(
            list(csv.DictReader(handle)), key=lambda row: (row["date"], row["description"])
        )
    rows = [{key: row[key] for key in ("date", "description", "amount", "type")} for row in rows]
    subset = []
    for name in ("NETFLIX", "SPOTIFY", "YOUTUBE", "ICLOUD", "APPLE MUSIC"):
        candidates = [row for row in rows if name in row["description"]]
        subset.extend(candidates[-3:])
    subset.sort(key=lambda row: (row["date"], row["description"]))
    (OUT / "text_single.pdf").write_bytes(make_pdf(rows))
    (OUT / "text_split.pdf").write_bytes(make_pdf(rows, split=True))
    (OUT / "ocr_source.pdf").write_bytes(make_pdf(subset, split=True))
    (OUT / "list_text.pdf").write_bytes(make_pdf(subset, list_style=True))
    hostile = [dict(row) for row in subset]
    hostile[0]["description"] = "<script>steal()</script>"
    (OUT / "hostile.pdf").write_bytes(make_pdf(hostile))
    encrypted = PdfWriter()
    encrypted.append(PdfReader(OUT / "text_single.pdf"))
    encrypted.encrypt(PASSWORD, algorithm="AES-256")
    with (OUT / "encrypted.pdf").open("wb") as handle:
        encrypted.write(handle)
    active = PdfWriter()
    active.append(PdfReader(OUT / "text_single.pdf"))
    active.add_js("app.alert('Synthetic inert active-content fixture');")
    active.add_attachment("synthetic.txt", b"synthetic attachment, not transaction data")
    with (OUT / "active_content.pdf").open("wb") as handle:
        active.write(handle)
    variants = [
        dict(file="text_single.pdf", rows=rows, kind="text"),
        dict(file="text_split.pdf", rows=rows, kind="text"),
        dict(file="list_text.pdf", rows=subset, kind="text"),
        dict(file="encrypted.pdf", rows=rows, kind="text", password=PASSWORD),
    ]
    with tempfile.TemporaryDirectory(prefix="subtrack-fixtures-") as directory:

        def render(source, dpi):
            path = Path(directory) / ("render" + str(dpi))
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-singlefile",
                    "-r",
                    str(dpi),
                    "-gray",
                    "-png",
                    str(source),
                    str(path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with Image.open(str(path) + ".png") as image:
                return image.copy().convert("L")

        base = render(OUT / "ocr_source.pdf", 200)
        for dpi, quality in ((150, 60), (150, 90), (200, 75), (200, 90), (300, 60), (300, 90)):
            image = render(OUT / "ocr_source.pdf", dpi)
            filename = f"scan_{dpi}_q{quality}.jpg"
            image.save(OUT / filename, quality=quality)
            variants.append(dict(file=filename, rows=subset, kind="ocr", dpi=dpi, quality=quality))
        for angle in (-2, 2):
            filename = f"skew_{angle}.jpg"
            base.rotate(angle, expand=True, fillcolor=255).save(OUT / filename, quality=75)
            variants.append(dict(file=filename, rows=subset, kind="ocr", dpi=200, skew=angle))
        noisy = base.copy()
        randomizer = random.Random(42)
        for _ in range(6000):
            noisy.putpixel(
                (randomizer.randrange(noisy.width), randomizer.randrange(noisy.height)),
                randomizer.choice((0, 255)),
            )
        noisy.save(OUT / "noise.jpg", quality=75)
        variants.append(dict(file="noise.jpg", rows=subset, kind="ocr", dpi=200))
        base.filter(ImageFilter.GaussianBlur(2)).save(OUT / "blur.jpg", quality=60)
        variants.append(dict(file="blur.jpg", rows=subset, kind="ocr", dpi=200))
        base.save(OUT / "clean.png")
        variants.append(dict(file="clean.png", rows=subset, kind="ocr", dpi=200))
        base.save(OUT / "scanned.pdf", resolution=200)
        variants.append(dict(file="scanned.pdf", rows=subset, kind="ocr", dpi=200))
        corrupt_pdf = Path(directory) / "corrupt.pdf"
        corrupt_pdf.write_bytes(make_pdf(subset, split=True, corrupt=True))
        render(corrupt_pdf, 200).save(OUT / "corrupt.jpg", quality=90)
        variants.append(
            dict(file="corrupt.jpg", rows=subset, kind="ocr", dpi=200, deliberate_corruption=True)
        )
        Image.new("L", (1600, 1000), 255).save(OUT / "unreadable.jpg", quality=60)
        variants.append(dict(file="unreadable.jpg", rows=subset, kind="ocr", reject=True))
    (OUT / "manifest.json").write_text(
        json.dumps(
            dict(
                source="../sample_transactions.csv", synthetic_only=True, seed=42, variants=variants
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Synthetic extraction corpus: {len(variants)} labelled variants; "
        f"{len(rows)} source rows; {len(subset)} OCR subset rows"
    )


if __name__ == "__main__":
    main()
