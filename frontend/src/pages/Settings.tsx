import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import { Dialog, ErrorState, Heading, Loading } from "../components/Common";
import { clearSession } from "../lib/session";
import { formatMoney } from "../lib/money";
export default function SettingsPage() {
  const budget = useQuery({
    queryKey: ["budget"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/budget", { signal })).data!,
  });
  const alerts = useQuery({
    queryKey: ["alert-settings"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/settings/alerts", { signal })).data!,
  });
  const [deleting, setDeleting] = useState(false);
  return (
    <>
      <Heading
        title="Make it yours"
        subtitle="Set a budget, choose your preferences and stay in control of your data."
      />
      <div className="settings-grid">
        <section className="panel">
          <h2>Monthly recurring budget</h2>
          <p className="muted">
            A limit for your subscriptions and fixed bills together.
          </p>
          {budget.isPending ? (
            <Loading />
          ) : budget.isError ? (
            <ErrorState
              error={budget.error}
              retry={() => {
                void budget.refetch();
              }}
            />
          ) : (
            <BudgetForm
              initial={budget.data.monthly_limit}
              saved={() => {
                void budget.refetch();
              }}
            />
          )}
        </section>
        <section className="panel">
          <h2>Renewal preferences</h2>
          <p className="notice-box">
            Preferences are saved now. Email delivery and budget alerts arrive
            in a later release; no alerts are being sent.
          </p>
          {alerts.isPending ? (
            <Loading />
          ) : alerts.isError ? (
            <ErrorState
              error={alerts.error}
              retry={() => {
                void alerts.refetch();
              }}
            />
          ) : (
            <AlertForm initial={alerts.data} />
          )}
        </section>
      </div>
      <section className="panel danger-zone">
        <h2>Your data, your control</h2>
        <p>
          Delete your account and all uploaded transactions, detected payments,
          preferences and stored data. This cannot be undone.
        </p>
        <button className="danger" onClick={() => setDeleting(true)}>
          Delete my data
        </button>
      </section>
      {deleting && <DeleteDialog onClose={() => setDeleting(false)} />}
    </>
  );
}
function BudgetForm({
  initial,
  saved,
}: {
  initial: string | null;
  saved: () => void;
}) {
  const [amount, setAmount] = useState(initial || "");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        if (!/^\d{1,10}(?:\.\d{1,2})?$/.test(amount)) {
          setError(
            "Enter a nonnegative INR amount with at most two decimal places.",
          );
          return;
        }
        setBusy(true);
        setError("");
        setMessage("");
        try {
          const result = await api.PUT("/api/v1/budget", {
            body: { monthly_limit: amount },
          });
          setMessage(
            `Budget saved: ${formatMoney(result.data!.monthly_limit!)}.`,
          );
          saved();
        } catch (caught) {
          setError(errorMessage(caught));
        } finally {
          setBusy(false);
        }
      }}
    >
      <p>
        {initial === null
          ? "No budget set yet."
          : `Current budget: ${formatMoney(initial)}`}
      </p>
      <label>
        Monthly limit (₹)
        <input
          inputMode="decimal"
          required
          pattern="\d{1,10}(\.\d{1,2})?"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </label>
      <button className="primary" disabled={busy}>
        {busy ? "Saving…" : "Save budget"}
      </button>
      {error && <ErrorState error={new Error(error)} />}
      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}
    </form>
  );
}
function AlertForm({
  initial,
}: {
  initial: components["schemas"]["AlertSettings"];
}) {
  const [days, setDays] = useState(String(initial.lead_time_days));
  const [email, setEmail] = useState(initial.notification_email || "");
  const [enabled, setEnabled] = useState(initial.enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        setMessage("");
        try {
          await api.PUT("/api/v1/settings/alerts", {
            body: {
              lead_time_days: Number(days),
              notification_email: email.trim() || null,
              enabled,
            },
          });
          setMessage("Preferences saved. Email delivery is not available yet.");
        } catch (caught) {
          setError(errorMessage(caught));
        } finally {
          setBusy(false);
        }
      }}
    >
      <label>
        Days before renewal
        <input
          type="number"
          required
          min={1}
          max={30}
          step={1}
          value={days}
          onChange={(event) => setDays(event.target.value)}
        />
      </label>
      <label>
        Notification email (optional)
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        Enable alerts when delivery becomes available
      </label>
      <button className="primary" disabled={busy}>
        {busy ? "Saving…" : "Save preferences"}
      </button>
      {error && <ErrorState error={new Error(error)} />}
      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}
    </form>
  );
}
export function DeleteDialog({ onClose }: { onClose: () => void }) {
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Dialog title="Delete your account data?" onClose={onClose}>
      <p>
        This permanently deletes your account and its data. Type{" "}
        <strong>DELETE</strong> to confirm.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (word !== "DELETE") return;
          setBusy(true);
          setError("");
          try {
            const result = await api.DELETE("/api/v1/me/data");
            clearSession(false, result.data!.deleted);
          } catch (caught) {
            setError(errorMessage(caught));
            setBusy(false);
          }
        }}
      >
        <label>
          Confirmation word
          <input
            value={word}
            onChange={(event) => setWord(event.target.value)}
            autoComplete="off"
          />
        </label>
        <div className="action-row">
          <button type="button" onClick={onClose} disabled={busy}>
            Keep my data
          </button>
          <button className="danger" disabled={word !== "DELETE" || busy}>
            {busy ? "Deleting…" : "Permanently delete data"}
          </button>
        </div>
        {error && <ErrorState error={new Error(error)} />}
      </form>
    </Dialog>
  );
}
