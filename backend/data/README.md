# Detector fixtures

All data here is synthetic. No personal bank statements are included.

- `sample_transactions.csv`: 399 rows generated with seed 42, as of 2026-10-18. Approximately
  ten months plus historical charges for two annual plans. Twelve subscription products,
  four fixed bills, salary/refund credits, irregular food/rides/shopping, billing drift,
  FX variation, a price increase, two Apple products, stopped gym payments.
- `ground_truth.json`: labels come from the generator's independent plan definitions,
  never from the detector. All amounts are decimal strings.
- `handwritten_bank.csv`: manually authored Indian-bank-shaped Withdrawal/Deposit export,
  semicolon-delimited, rail/reference/city noise, drifting dates, salary/food/rides traps,
  three malformed rows, untrusted spreadsheet-formula description.
- `handwritten_products.csv`: manually authored Debit/Credit export, comma-delimited,
  three date representations, thousands separators, generic Apple billing at two price
  levels, yearly Microsoft, FX Adobe, stopped Cultfit, irregular Swiggy and salary.
- `*_ground_truth.json`: independent handwritten product/cadence/category/amount labels.
- `evaluation_report.json`: recorded output of the evaluation command. Re-run to refresh.

These handwritten fixtures represent common bank column layouts; they are not certified exports
from a particular bank, and no real-customer accuracy claim is made.

From `backend`:

```sh
python scripts/gen_sample_data.py
python scripts/evaluate_detector.py --json-output data/evaluation_report.json
python -m pytest -q
```

`make sample` and `make evaluate` run the same commands in Compose. `make sample` writes to
the bind-mounted data directory. The default as-of date is fixed for reproducibility; pass
`--as-of YYYY-MM-DD` and `--seed N` to generate another period. The future demo loader must
regenerate relative to its demo clock rather than silently treating this fixture as current.

The evaluation matches one-to-one on merchant, cadence, kind, currency, and amount to one paisa.
It also verifies category, occurrences, last charge, stopped status, and price signal where
labelled. False detections among negative rows count as false positives. It exits nonzero for
F1 below 0.9, any labelled-attribute mismatch, any unmatched product, or unexpected skipped rows.
CI runs the same evaluation. Twenty additional random seeds are exercised by pytest.

