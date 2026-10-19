# Three-minute demo

Recorded example: application clock **2026-10-18, Asia/Kolkata**, seed 42, offline assistant,
console notifier. The real loader defaults to current application today, not this fixed date.
For exact replay only, set APP_TEST_AS_OF=2026-10-18 in the private development .env before startup;
clear it and restart afterward. Production refuses test clocks. `make e2e` fixes/restores this clock
explicitly and runs the same clicks/jobs in demo.spec.ts. Other dates can change row counts, costs
and renewals; use the actual API/UI, never present this table as today's data.

Prerequisites outside the timed tour: follow README setup, `docker compose up --build --wait`,
`make seed`; keep a terminal in the repo and a browser at localhost:5173. Initial builds need
network/package caches; this installed demo needs no AI key, bank connection or SMTP server.

| Measured on the example clock | Expected value |
| --- | --- |
| Imported / duplicate / malformed rows | 399 / 0 / 0 |
| Detected recurring products | 16: 12 subscriptions, 4 fixed bills |
| Monthly equivalent, all recurring | ₹26,312.85 |
| Annual equivalent, all recurring | ₹3,15,754.24 |
| Subscription monthly equivalent | ₹4,015.80 |
| Fixed bills monthly equivalent | ₹22,297.05 |
| Potential monthly saving, open overlap items | ₹343.00 |
| Duplicate music saving | ₹119.00 |
| Default missing budget | ₹26,212.85 |
| This week's renewal | newspaper, ₹49.00, 2026-10-22 |
| First upcoming email send_on | 2026-10-19 (three days before newspaper) |

1. **0:00–0:20 — Register and load.** Select Create account, enter a synthetic unique example.org
   email and a 12+ character password with three classes; submit. On Overview select **Load demo
   data**. Watch real queued/parsing/ingesting/detecting progress, then Statement processed:
   399 inserted, zero duplicates/malformed, 16 products. Select **Dismiss import result**.
   **Say:** “This CSV is generated for the displayed demo date and uses the same import pipeline.”

2. **0:20–0:40 — Overview.** Point to the recorded monthly/yearly figures above, 12 active
   subscriptions, fixed bills separately and ₹343.00 potential monthly saving. Use Show data tables
   if charts are inconvenient. The Demo data badge states the clock; the theme menu offers system,
   light and dark. **Say:** “Every amount comes from deterministic Decimal calculations in the API.”

3. **0:40–1:00 — Review products.** Open Subscriptions. The two Apple products have distinct
   charges. Open a Review drawer, inspect charge history/confidence, close with Escape. Find Cultfit:
   “May have stopped · 4 missed cycles” is a notice; its status remains active. Netflix has the
   possible price increase ₹199.00 → ₹219.00. **Say:** “These are reviewable detections, not certainty.”

4. **1:00–1:15 — Recommendation.** Open Recommendations. Locate the music overlap between Apple
   and Spotify, estimated monthly saving ₹119.00. Accept records review intent only; it never changes
   the subscription status. **Say:** “You may want to review overlap; this is not advice to cancel.”

5. **1:15–1:40 — Ask a grounded question.** Select **Ask SubTrack**, then **What renews this week?**
   and **Send question**. Tool status appears, followed by newspaper, ₹49.00 and 2026-10-22, with
   “Based on: upcoming renewals”. Close with Escape. **Say:** “Offline mode uses built-in rules and
   real read-only tools; figures are checked before any answer text is shown.”

6. **1:40–2:10 — Produce a renewal email.** Open Settings. First save Monthly limit **99999.00**
   so the deliberately below-total demo budget does not send before the budget step. Keep enabled
   alerts, default lead 3 and synthetic recipient demo@example.org. In the terminal run:

   ```sh
   make run-alerts AS_OF=2026-10-19
   make outbox
   ```

   Open the newspaper renewal `.eml` from var/outbox/<user UUID>/<alert UUID>.eml in a mail/text viewer;
   it contains plaintext and HTML plus the educational notice. Refresh Settings to see sent status.
   Run the same job again: there is still one artifact for that alert. Other synthetic accounts can
   also have mail; the guarantee is **per user and alert**, not one file across the entire volume.
   **Say:** “The dev notifier produces a real email artifact; SMTP has documented at-least-once semantics.”

7. **2:10–2:35 — Budget email.** Save Monthly limit **1.00**, run the same dated job and `make outbox`.
   The budget message shows total ₹26,312.85, budget ₹1.00, overage ₹26,311.85 and contributors.
   Re-running cannot create a second budget alert for this user/calendar month. Refresh the recent
   alerts panel to see it sent. **Say:** “The existing summary service supplies the overage; no LLM arithmetic.”

8. **2:35–3:00 — Privacy.** Select **Delete my data**, type **DELETE**, then **Permanently delete
   data**. Login appears with returned deletion counts. Chat and private console copies are gone.
   The exported var/outbox copies from this tour remain under your control; remove them yourself
   when finished. **Say:** “Account deletion is scoped. Already exported files or delivered inbox
   emails cannot be recalled.” Clear APP_TEST_AS_OF and restart for normal current-date demos.

## Fallback

- Slow import: show real progress; do not invent completion. Use the pre-seeded dev login from README
  to continue presenting, then investigate the safe upload error afterward.
- No live provider/key: the default offline assistant is the intended fallback, accurately labelled.
- No SMTP: the private console outbox is the intended demo mailer. Do not claim an inbox delivery.
- No due renewal today: read the planned send_on from Settings/API and use that explicit CLI date
  with synthetic data. Never alter real transactions or silently move the application clock.
- Bad network at presentation time: prepare images/packages/browsers first. Runtime default demo is local.
- If a test fails, preserve the ignored trace privately; report the failure and do not claim a green release.

The automated script checks independent integer/Decimal expectations, actual tool results, outbox
idempotency and final deletion. Manual timing assumes the stack is already healthy; build time is excluded.
