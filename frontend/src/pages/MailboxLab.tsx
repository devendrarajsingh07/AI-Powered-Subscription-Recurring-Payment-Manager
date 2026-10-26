import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import {
  Dialog,
  Empty,
  ErrorState,
  Heading,
  Loading,
} from "../components/Common";
import { formatMoney } from "../lib/money";

type Evidence = components["schemas"]["ReceiptEvidenceOut"];
type Decision = components["schemas"]["EvidenceDecision"];
type Category = components["schemas"]["InterestPut"]["categories"][number];

export default function MailboxLab() {
  const cache = useQueryClient();
  const [consent, setConsent] = useState(false);
  const [syncId, setSyncId] = useState<string>();
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [word, setWord] = useState("");
  const [notice, setNotice] = useState("");
  const [status, setStatus] = useState<"pending" | "matched" | "ignored">(
    "pending",
  );
  const [offset, setOffset] = useState(0);
  const config = useQuery({
    queryKey: ["mailbox", "config"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/mailbox/config", { signal })).data!,
    retry: false,
  });
  const connected = !!config.data?.connected;
  const enabled = !!config.data?.enabled;
  const progress = useQuery({
    queryKey: ["mailbox", "sync", syncId],
    enabled: !!syncId,
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/mailbox/sync/{sync_id}", {
          signal,
          params: { path: { sync_id: syncId! } },
        })
      ).data!,
    refetchInterval: (query) =>
      ["done", "failed", "cancelled"].includes(
        query.state.data?.status || "queued",
      )
        ? false
        : 1500,
    retry: false,
  });
  const rows = useQuery({
    queryKey: ["mailbox", "evidence", status, offset],
    enabled: enabled && connected,
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/mailbox/evidence", {
          signal,
          params: { query: { status, offset, limit: 10 } },
        })
      ).data!,
  });
  useEffect(() => {
    if (progress.data?.status === "done")
      void cache.invalidateQueries({ queryKey: ["mailbox", "evidence"] });
  }, [progress.data?.status, cache]);
  const connect = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/mailbox/synthetic/connect", {
          body: { consent: true, version: config.data!.consent_version },
        })
      ).data!,
    onSuccess: (value) => {
      cache.setQueryData(["mailbox", "config"], value);
      setConsent(false);
      setNotice(
        "Synthetic rehearsal connected. No Google account was accessed.",
      );
    },
  });
  const sync = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/mailbox/sync")).data!,
    onSuccess: (value) => {
      setSyncId(value.id);
      cache.setQueryData(["mailbox", "sync", value.id], value);
      setNotice("");
    },
  });
  const disconnect = useMutation({
    mutationFn: async () =>
      (await api.DELETE("/api/v1/mailbox/connection")).data!,
    onSuccess: () => {
      setSyncId(undefined);
      setConfirmDisconnect(false);
      setWord("");
      cache.removeQueries({ queryKey: ["mailbox", "evidence"] });
      cache.removeQueries({ queryKey: ["mailbox", "sync"] });
      void cache.invalidateQueries({ queryKey: ["mailbox", "config"] });
      setNotice(
        "Mailbox consent withdrawn; evidence and sync records purged. Bank history is unchanged.",
      );
    },
  });
  const decision = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Decision }) =>
      (
        await api.PATCH("/api/v1/mailbox/evidence/{evidence_id}", {
          params: { path: { evidence_id: id } },
          body,
        })
      ).data!,
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["mailbox", "evidence"] });
      setNotice("Receipt decision saved. Spending totals are unchanged.");
    },
  });

  if (config.isPending)
    return <Loading text="Checking mailbox availability…" />;
  if (config.isError)
    return (
      <ErrorState error={config.error} retry={() => void config.refetch()} />
    );
  return (
    <>
      <Heading
        title="Receipt inbox lab"
        subtitle="Offline synthetic rehearsal — no Gmail account or inbox access."
      />
      <section className="panel">
        <h2>Separate evidence, correct totals</h2>
        <p className="notice-box">{config.data.disclosure}</p>
        <p>
          Receipt evidence is excluded from spend, detection and savings. Bank
          matches are suggestions until you explicitly confirm one. Email
          authenticity is not verified.
        </p>
        <p>
          Live Gmail is unavailable pending owner and Google approvals. No email
          bodies are displayed, stored or sent to AI.
        </p>
        {!enabled && (
          <Empty>
            This lab is disabled. It can be enabled only for local synthetic
            development; the public demo stays synthetic-data-only.
          </Empty>
        )}
        {enabled && !connected && (
          <>
            <label className="check-label">
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
              />
              I consent to the synthetic mailbox rehearsal described above
            </label>
            <button
              className="primary"
              disabled={!consent || connect.isPending}
              onClick={() => connect.mutate()}
            >
              Start synthetic mailbox lab
            </button>
          </>
        )}
        {connected && (
          <>
            <span className="badge">Synthetic fixture connection</span>{" "}
            {enabled && (
              <button
                disabled={
                  sync.isPending ||
                  ["queued", "running"].includes(progress.data?.status || "")
                }
                onClick={() => sync.mutate()}
              >
                Sync synthetic receipts
              </button>
            )}{" "}
            <button onClick={() => setConfirmDisconnect(true)}>
              Disconnect and remove evidence
            </button>
          </>
        )}
        {(connect.isPending || sync.isPending) && (
          <Loading text="Saving your request…" />
        )}
        {notice && <p role="status">{notice}</p>}
        {connect.isError && <ErrorState error={connect.error} />}
        {sync.isError && <ErrorState error={sync.error} />}
      </section>
      {syncId && (
        <section className="panel" aria-label="Mailbox sync progress">
          <h2>Real sync progress</h2>
          {progress.isPending ? (
            <Loading />
          ) : progress.isError ? (
            <ErrorState
              error={progress.error}
              retry={() => void progress.refetch()}
            />
          ) : (
            <div role="status" aria-live="polite">
              <p>Status: {progress.data.status}</p>
              <progress
                aria-label="Synthetic receipts processed"
                max={progress.data.total || 1}
                value={progress.data.processed}
              />
              <p>
                {progress.data.processed} / {progress.data.total} processed ·{" "}
                {progress.data.accepted} new evidence ·{" "}
                {progress.data.duplicates} duplicates · {progress.data.rejected}{" "}
                unsupported receipts
              </p>
              {progress.data.status === "queued" && (
                <p>
                  Waiting for the separate local worker. You can leave this
                  page; evidence will be available on return.
                </p>
              )}
              {progress.data.failure_code && (
                <p className="notice-box">
                  Sync could not complete: {progress.data.failure_code}. You may
                  retry a terminal failed sync; no partial charge was created.
                </p>
              )}
            </div>
          )}
        </section>
      )}
      {enabled && connected && (
        <section className="panel">
          <h2>Review receipt evidence</h2>
          <label>
            Evidence status
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as typeof status);
                setOffset(0);
              }}
            >
              <option value="pending">Needs review</option>
              <option value="matched">Matched to bank</option>
              <option value="ignored">Ignored</option>
            </select>
          </label>
          {decision.isError && <ErrorState error={decision.error} />}
          {rows.isPending ? (
            <Loading />
          ) : rows.isError ? (
            <ErrorState error={rows.error} retry={() => void rows.refetch()} />
          ) : (
            <>
              <p>
                {rows.data.total} receipt evidence records · excluded from
                spending totals
              </p>
              {!rows.data.items.length ? (
                <Empty>
                  No evidence in this view. Sync synthetic receipts or choose a
                  different status.
                </Empty>
              ) : (
                rows.data.items.map((row) => (
                  <EvidenceEditor
                    key={`${row.id}:${row.merchant}:${row.charged_on}:${row.amount}:${row.status}`}
                    row={row}
                    busy={decision.isPending}
                    onDecision={(body) => decision.mutate({ id: row.id, body })}
                  />
                ))
              )}
              <div className="review-toolbar">
                <button
                  disabled={!offset}
                  onClick={() => setOffset((value) => Math.max(0, value - 10))}
                >
                  Previous evidence
                </button>
                <button
                  disabled={offset + 10 >= rows.data.total}
                  onClick={() => setOffset((value) => value + 10)}
                >
                  Next evidence
                </button>
              </div>
            </>
          )}
        </section>
      )}
      {enabled && (
        <Interests
          version={config.data.interest_version}
          disclosure={config.data.interest_disclosure}
        />
      )}
      {confirmDisconnect && (
        <Dialog
          title="Disconnect synthetic mailbox?"
          onClose={() => {
            if (!disconnect.isPending) setConfirmDisconnect(false);
          }}
        >
          <p>
            This permanently removes mailbox evidence, cancels sync and clears
            local mailbox credentials. Bank transactions and voluntary plan
            interests are separate. Type DISCONNECT.
          </p>
          <label>
            Confirmation word
            <input
              value={word}
              onChange={(event) => setWord(event.target.value)}
              autoComplete="off"
            />
          </label>
          <button
            disabled={word !== "DISCONNECT" || disconnect.isPending}
            onClick={() => disconnect.mutate()}
          >
            Purge mailbox evidence
          </button>
          {disconnect.isPending && <Loading />}
          {disconnect.isError && <ErrorState error={disconnect.error} />}
        </Dialog>
      )}
    </>
  );
}

export function EvidenceEditor({
  row,
  busy,
  onDecision,
}: {
  row: Evidence;
  busy: boolean;
  onDecision: (body: Decision) => void;
}) {
  const [merchant, setMerchant] = useState(row.merchant || "");
  const [day, setDay] = useState(row.charged_on || "");
  const [amount, setAmount] = useState(row.amount || "");
  const [reviewed, setReviewed] = useState(false);
  const [selected, setSelected] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const dirty =
    merchant !== (row.merchant || "") ||
    day !== (row.charged_on || "") ||
    amount !== (row.amount || "");
  function resetApproval() {
    setReviewed(false);
    setConfirmed(false);
    setSelected("");
  }
  return (
    <article
      data-testid={row.id}
      className="panel"
      aria-label={`Receipt evidence ${row.merchant || "unknown merchant"}`}
    >
      <h3>{row.merchant || "Merchant needs review"}</h3>
      <span className="badge">{row.status} · authenticity unverified</span>
      <p>
        {row.amount ? formatMoney(row.amount) : "Amount unknown"} ·{" "}
        {row.charged_on || "Payment date unknown"}
      </p>
      <details>
        <summary>Extraction notices</summary>
        <ul>
          {row.flags.map((flag) => (
            <li key={flag}>{flag.replaceAll("_", " ")}</li>
          ))}
        </ul>
      </details>
      <fieldset disabled={busy}>
        <legend>Correct receipt fields</legend>
        <label>
          Merchant
          <input
            value={merchant}
            maxLength={100}
            onChange={(event) => {
              setMerchant(event.target.value);
              resetApproval();
            }}
          />
        </label>
        <label>
          Payment date
          <input
            type="date"
            value={day}
            onChange={(event) => {
              setDay(event.target.value);
              resetApproval();
            }}
          />
        </label>
        <label>
          Amount (INR)
          <input
            inputMode="decimal"
            value={amount}
            onChange={(event) => {
              setAmount(event.target.value);
              resetApproval();
            }}
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(event) => setReviewed(event.target.checked)}
          />
          I reviewed these receipt fields
        </label>
        <p className="muted">
          Saving corrections clears any previous bank link. It never creates a
          bank transaction.
        </p>
        <button
          disabled={
            !reviewed ||
            !merchant.trim() ||
            !day ||
            !/^\d{1,10}(?:\.\d{1,2})?$/.test(amount)
          }
          onClick={() =>
            onDecision({
              action: "review",
              verified: true,
              merchant,
              charged_on: day,
              amount,
            })
          }
        >
          Save reviewed fields
        </button>
      </fieldset>
      <fieldset disabled={busy || dirty}>
        <legend>Confirm a bank match</legend>
        {dirty && <p>Save corrected fields before choosing a bank match.</p>}
        {!row.candidates.length ? (
          <p>
            No matching bank debit found. Upload a synthetic bank statement or
            leave this unresolved. No charge is inferred.
          </p>
        ) : (
          <>
            {row.candidates.length > 1 && (
              <p className="notice-box">
                Several bank debits qualify. Select the same payment explicitly;
                no match is automatic.
              </p>
            )}
            {row.candidates.map((candidate) => (
              <label className="check-label" key={candidate.id}>
                <input
                  type="radio"
                  name={`match-${row.id}`}
                  value={candidate.id}
                  checked={selected === candidate.id}
                  onChange={() => {
                    setSelected(candidate.id);
                    setConfirmed(false);
                  }}
                />
                {candidate.merchant_normalized} · {candidate.date} ·{" "}
                {formatMoney(candidate.amount)}
              </label>
            ))}
            <label className="check-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              I confirm this is the same payment
            </label>
            <button
              disabled={!confirmed || !selected}
              onClick={() =>
                onDecision({
                  action: "match",
                  verified: true,
                  transaction_id: selected,
                })
              }
            >
              Confirm bank match
            </button>
          </>
        )}
      </fieldset>
      <button
        disabled={busy}
        onClick={() => onDecision({ action: "ignore", verified: false })}
      >
        Ignore this evidence
      </button>
    </article>
  );
}

function Interests({
  version,
  disclosure,
}: {
  version: string;
  disclosure: string;
}) {
  const cache = useQueryClient();
  const [notice, setNotice] = useState(false);
  const query = useQuery({
    queryKey: ["plan-interest"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/interests", { signal })).data!,
  });
  if (query.isPending)
    return <Loading text="Opening voluntary interest preferences…" />;
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return (
    <>
      {notice && (
        <p role="status">
          Interest preferences saved. No provider was contacted.
        </p>
      )}
      <InterestForm
        key={query.data.categories.join(",")}
        initial={query.data.categories}
        version={version}
        disclosure={disclosure}
        onSaved={() => {
          setNotice(true);
          void cache.invalidateQueries({ queryKey: ["plan-interest"] });
        }}
      />
    </>
  );
}

function InterestForm({
  initial,
  version,
  disclosure,
  onSaved,
}: {
  initial: Category[];
  version: string;
  disclosure: string;
  onSaved: () => void;
}) {
  const [categories, setCategories] = useState(initial);
  const [consent, setConsent] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      api.PUT("/api/v1/interests", {
        body: { consent: true, version, categories },
      }),
    onSuccess: onSaved,
  });
  const remove = useMutation({
    mutationFn: () => api.DELETE("/api/v1/interests"),
    onSuccess: onSaved,
  });
  return (
    <section className="panel" aria-label="Voluntary plan interest">
      <h2>Optional group-plan interest</h2>
      <p className="notice-box">{disclosure}</p>
      <fieldset disabled={save.isPending || remove.isPending}>
        <legend>Your own declarations — never inferred from receipts</legend>
        {(["music", "streaming", "cloud"] as const).map((category) => (
          <label className="check-label" key={category}>
            <input
              type="checkbox"
              checked={categories.includes(category)}
              onChange={(event) =>
                setCategories((current) =>
                  event.target.checked
                    ? [...current, category]
                    : current.filter((item) => item !== category),
                )
              }
            />
            {category}
          </label>
        ))}
        <label className="check-label">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />
          I separately consent to save these voluntary interests
        </label>
        <button disabled={!consent} onClick={() => save.mutate()}>
          Save voluntary interests
        </button>{" "}
        <button onClick={() => remove.mutate()}>Withdraw all interests</button>
      </fieldset>
      {(save.isPending || remove.isPending) && (
        <Loading text="Saving interest preferences…" />
      )}
      {save.isError && <ErrorState error={save.error} />}
      {remove.isError && <ErrorState error={remove.error} />}
    </section>
  );
}
