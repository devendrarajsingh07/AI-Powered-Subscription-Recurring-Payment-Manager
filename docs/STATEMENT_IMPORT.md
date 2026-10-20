# Statement import — measured demo scope

CSV, text-layer PDFs, scanned PDFs, JPEG and PNG share the existing deterministic ingestion,
detection, recommendation and alert-planning pipeline. Extraction uses local programs on the API
server; no statement is sent to Gemini or a cloud OCR service. Use synthetic data for demonstrations.
This remains a single-instance development stack, not a safe public upload service.

## Use it

On Upload, choose a statement. CSV retains its column-mapping flow. For PDF/image input, optionally
enter the PDF password, select Preview, and wait for real page progress. An encrypted file without
the right password fails safely; Retry lets you enter a password without putting it in a URL.

Compare the local preview with every extracted row. Edit dates, descriptions, decimal-string amounts
and debit/credit type; verify each row, or remove it. Changing a verified row resets its verification.
The explicit bulk acknowledgment means you have reviewed **every** row, including paginated rows.
Import stays disabled until every flagged row is verified or removed. Server validation is final;
flagged rows submitted without verification are excluded and counted. Never equate a high OCR score
or matched balance with a correct digit. Every extracted row, including text PDFs, requires review.

The local image/PDF preview is a browser object URL, revoked on cleanup. Some browsers cannot show
PDFs inside the sandboxed frame; the local-copy link opens the same browser-held file. It is not a
server download. The server preserves the extracted description through the existing raw-description
storage path; formula-leading characters are neutralized only when echoed in the preview.

## Limits and supported layouts

| Input/resource | Default / hard maximum |
| --- | --- |
| CSV | 5 MB, 50,000 rows; existing malformed/unreadable-remainder handling |
| PDF | 10 MB, 30 pages |
| JPEG/PNG | 10 MB, 25 megapixels, checked before decoding |
| Extracted table | 5,000 rows, 1,000 characters per description; truncation flagged |
| Extraction | 20 seconds/page; 120 seconds total; 512 MB address-space limit |
| Preview | 30-minute TTL; 20 attempts/user/UTC day; 2 concurrent/user; 4 globally |

Corresponding `STATEMENT_*` variables are listed in `.env.example`; validation prevents exceeding
the file/page/pixel/time/TTL maxima. Memory can be configured up to 1,024 MB. Quota counters persist
independently of previews so cancel/expiry does not reset them. They store counts, never row text.

Supported English layouts: aligned single amount with Dr/Cr, separate withdrawal/deposit with an
optional running balance, and a lower-confidence one-line list fallback. Wrapped descriptions and
repeated headings are handled. Indian grouping such as `1,23,456.78` uses the existing Decimal CSV
parser; Dr/Cr is translated to debit/credit. Only INR is supported: users must verify the statement
currency; extraction does not reliably identify a foreign currency printed elsewhere on the page.

Clean scans/screenshots around 200 dpi or better are the target. Phone photos, handwriting, heavy
skew/blur, app UI screenshots and unfamiliar bank layouts are unsupported/best effort and may be
rejected. Pages with no readable transaction rows, including cover-only pages, currently fail with
guidance. Excel is unsupported; export CSV or an eligible PDF instead. Real-bank coverage is unmeasured.

## Evaluation, 2026-10-20

`make evaluate-extraction` runs the committed synthetic matrix. Labels come from the sample
transactions, not detector output. Exact row identity uses date, Decimal amount and debit/credit;
description accuracy is reported separately. Field comparisons are positional, so a dropped row
penalizes subsequent field matches. The table reports fractions, not confidence scores.

| Variant | Rows | Row precision/recall | Date | Amount | Description | Reconciliation |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| text_single.pdf | 399 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | unavailable |
| text_split.pdf | 399 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| list_text.pdf | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | unavailable |
| encrypted.pdf | 399 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | unavailable |
| scan_150_q60.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| scan_150_q90.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 0.933 | matched |
| scan_200_q75.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| scan_200_q90.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| scan_300_q60.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 0.867 | matched |
| scan_300_q90.jpg | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| skew_-2.jpg | 15 | 0.800 / 0.800 | 0.867 | 0.800 | 0.600 | mismatch |
| skew_2.jpg | 0 | 0 / 0 | 0 | 0 | 0 | rejected |
| noise.jpg | 0 | 0 / 0 | 0 | 0 | 0 | rejected |
| blur.jpg | 0 | 0 / 0 | 0 | 0 | 0 | rejected |
| clean.png | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| scanned.pdf | 15 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | matched |
| corrupt.jpg | 15 | 0.933 / 0.933 | 1.000 | 0.933 | 1.000 | mismatch |
| unreadable.jpg | 0 | 0 / 0 | 0 | 0 | 0 | rejected |

All returned rows were flagged (rate 1.000); rejected variants return none. Silent errors: **0**,
with **zero automatically accepted rows**. This is a conservative review guarantee, not perfect
extraction accuracy. CI requires zero silent errors, clean text aggregate field accuracy >=99%,
and rejection of the explicitly unreadable case. The measured synthetic floor for >=95% row/date/
amount accuracy is 150 dpi on clean variants; it is not a universal minimum or a real-bank claim.
Description mistakes remain at some JPEG qualities even when amounts and balances match.

## Private local check

Keep your own redacted files outside git (or in ignored `private-statements/`). Do not upload them
to the coding agent or attach them to issues. Build the API image with `make dev` first. This tested
PowerShell command mounts just one file read-only; substitute your own absolute path:

```powershell
$fixture=(Resolve-Path backend/data/extraction/list_text.pdf).Path
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m --mount "type=bind,source=$fixture,target=/input/statement.pdf,readonly" subtrack-api python scripts/check_extraction.py /input/statement.pdf
```

Linux/macOS: use an absolute source path in the same Docker `--mount` argument. Add `-it` and
`--password` after the filename for a private terminal password prompt. Never pass the actual
password as a command argument. Output is escaped terminal JSON only; no result file, database or
network access. Temporary extraction files exist in the disposable tmpfs during processing and are
removed. Terminal scrollback can still be sensitive. Compare rows, flags and balances yourself;
report only content-free aggregate findings. The script requires Linux/Docker, not native Windows.

## Dependencies and isolation

Installed Python metadata: pdfminer.six 20260107 (MIT), pypdf 6.21.1 (BSD-3-Clause), Pillow 13.0.0
(MIT-CMU), ReportLab 5.0.1 (BSD); new transitives cryptography 50.0.2 (Apache-2.0 OR BSD-3-Clause),
cffi 2.1.1 (MIT-0), charset-normalizer 3.5.2 (MIT). Pins/hashes are in `requirements.lock`.
Installed Debian copyright files identify Tesseract as Apache-2.0 and poppler's main source as GPL-2,
with component GPL-2-or-GPL-3/GPL-3/Apache-2.0 notices. Poppler is a separate CLI, not linked into
Python. Preserve distribution notices and review obligations before redistributing images. No AGPL
library was added; this list does not choose a project license. The owner selected MIT; application
of that choice remains a human task under the instruction not to add a LICENSE file in this phase.

Measured API image: 646,058,096 bytes; runtime uid/gid 1000. Parser subprocesses receive no DB or
provider credentials, use argument lists, resource limits, deadlines and process-group termination.
Original files live in memory/private temporary directories; normal completion/cancel/timeout cleans
them, and single-instance startup removes abandoned extraction directories. This is not a hardened
sandbox: outbound networking is not blocked by an OS policy in Compose, and API and parser share
the container. No parser code makes network calls. Phase 8 needs a separate no-network worker,
durable jobs, cgroup limits and shared caps before accepting real users.
