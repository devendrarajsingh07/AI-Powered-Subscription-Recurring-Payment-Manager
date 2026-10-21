import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";

type Category = components["schemas"]["SupportReportIn"]["category"];

export function ReportProblem() {
  const [category, setCategory] = useState<Category>("bug");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  return (
    <section className="panel">
      <h2>Report a problem</h2>
      <p className="muted">
        Describe what went wrong. Do not include bank statements, account or
        card numbers, or amounts — the form rejects them.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          setSent(false);
          try {
            await api.POST("/api/v1/support/reports", {
              body: { category, message: text.trim() },
            });
            setText("");
            setSent(true);
          } catch (caught) {
            setError(errorMessage(caught));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          What kind of problem?
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value as Category)}
          >
            <option value="bug">Something is broken</option>
            <option value="data_issue">Something looks wrong</option>
            <option value="account">Account or sign-in</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Description
          <textarea
            required
            minLength={10}
            maxLength={1000}
            rows={4}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <button className="primary" disabled={busy || text.trim().length < 10}>
          {busy ? "Sending…" : "Send report"}
        </button>
        {sent && (
          <p className="success" role="status">
            Thanks — your report was received.
          </p>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
