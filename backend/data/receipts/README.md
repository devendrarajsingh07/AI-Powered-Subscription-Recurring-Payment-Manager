# Synthetic receipt fixtures only

These 16 MIME messages were authored for tests. Addresses use reserved example.org domains;
merchant labels are fictional test inputs, not copies of real providers' email templates.
Ground truth records explicit plan inputs independently of the parser. Eight labelled paid
receipts drive the integration demo: Netflix monthly, Spotify monthly, Google One yearly.
The remaining cases cover ambiguity, missing evidence, hostile HTML, refunds and failed/due
payments. Every accepted candidate still needs explicit review.

Never put real email or statements here. Use the ignored private-emails/ directory for any
future owner-operated local checks. App outbox files remain ignored. The narrow Git ignore
exception and CI scan allow only the EML filenames listed in ground_truth.json.

Run `make evaluate-receipts` from the repository root. Successful fixture outcomes do not
establish real-provider accuracy, message authenticity or payment settlement.
