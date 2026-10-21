# WP4 implementation decisions — planned, not completion evidence

The owner requires WP3 local gates and hosted CI before WP4 implementation. Keep PostgreSQL;
no Redis, paid services, provider calls or real data. This records the next design before building.

- Add an owned durable-job table: bounded encrypted input, immutable explicit as-of date,
  queued/running/done/dead-letter/cancelled status, attempt/backoff/TTL, claim UUID and lease.
  Claim with FOR UPDATE SKIP LOCKED; heartbeat independently; stale claims cannot publish results.
  Final ingestion, job acknowledgement and input removal share the same DB transaction. Dedupe and
  user decisions continue through existing repositories/detector/insight services.
- Coordinate queue capacity, user quotas and chat in-flight/request caps in PostgreSQL. Auth and
  model tools never accept a caller-selected user ID. Global maintenance enumerates IDs only.
- Separate worker service polls PostgreSQL; API enqueues accepted work, never depends on a
  BackgroundTasks callback to make an accepted upload durable. Keep explicit stage/progress and
  safe terminal/dead-letter visibility. Remove general interrupted-upload failure recovery only
  after worker-kill/lease-retry tests pass.
- Original bytes persist only as bounded authenticated ciphertext until completion, failure,
  cancellation, TTL or deletion. Use the already locked cryptography package; no new cipher/SDK.
  Domain-separated key derivation from the strong environment signing secret avoids a published
  default encryption key. Document that emergency signing-key rotation makes pending input
  undecryptable: fail safely/remove it; normally drain work before rotation. No financial writes
  may partially commit. Production remains blocked independently.
- A restricted extraction service has no DB credentials or key, no Docker socket, read-only root,
  bounded tmpfs/CPU/memory/PIDs, dropped capabilities and no new privileges. It joins only an
  internal network; disable upstream DNS forwarding as well as external routing. Worker passes
  bounded input and validates bounded structured output. All OCR rows still require human review.
- Preserve the earlier **password is memory-only, never stored** guarantee. For encrypted PDFs,
  bounded decryption preflight runs in the restricted service before durable job acceptance;
  queue only its decrypted PDF under authenticated encryption, never the password. If preflight
  or the submitting API dies before acknowledgement, retry the request/re-enter the password.
  Do not acknowledge a durable job that still depends on an in-memory password.
- Local Compose must exercise two API instances, one worker and the restricted extraction service
  against one PostgreSQL. Existing pure/legacy test harnesses do not replace that integration gate.
  The free hosted public demo may retain its explicitly labelled synthetic-only inline fallback;
  no file uploads are enabled there. A separate deployed worker remains owner-blocked.
- Tests must cover lease expiry/stale publication, crash retry/no duplicates, capacity shared across
  APIs, safe corrupt/expired payload failure, every input deletion path, queued/running account
  deletion, actual container network/credential restrictions and existing CSV/PDF/OCR browser flows.

This plan is not a claim that any WP4 control exists. Update DOD with actual commands/results only.
