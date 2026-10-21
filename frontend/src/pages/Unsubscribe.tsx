import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, errorMessage } from "../api/client";

export function Unsubscribe() {
  const [params] = useSearchParams();
  const u = params.get("u") || "";
  const t = params.get("t") || "";
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  return (
    <main className="fatal">
      <h1>Turn off SubTrack alert emails</h1>
      {u && t ? (
        <>
          <p>
            This stops renewal and budget alert emails for the account that sent
            you this link. You can turn them back on in Settings after signing
            in.
          </p>
          <button
            className="primary"
            disabled={busy || !!message}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const result = await api.POST("/api/v1/alerts/unsubscribe", {
                  params: { query: { u, t } },
                });
                setMessage(result.data!.message);
              } catch (caught) {
                setError(errorMessage(caught));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Working…" : "Turn off alert emails"}
          </button>
        </>
      ) : (
        <p role="alert">This unsubscribe link is incomplete.</p>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      <p>
        <Link to="/login">Go to SubTrack</Link>
      </p>
    </main>
  );
}
