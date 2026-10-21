import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { api, errorMessage } from "../api/client";
import { passwordError } from "./Auth";

export function AccountRecovery({ kind }: { kind: "verify" | "reset" }) {
  const location = useLocation();
  const [email, setEmail] = useState(
    (location.state as { email?: string } | null)?.email || "",
  );
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<string>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setMessage(await action());
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  async function request(event: FormEvent) {
    event.preventDefault();
    await run(
      async () =>
        (
          await api.POST(
            kind === "verify"
              ? "/api/v1/auth/email/request"
              : "/api/v1/auth/password/request",
            { body: { email } },
          )
        ).data!.message,
    );
  }
  async function confirm(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      if (kind === "reset") {
        const invalid = passwordError(password, true);
        if (invalid) throw new Error(invalid);
        return (
          await api.POST("/api/v1/auth/password/reset", {
            body: { token: code, password },
          })
        ).data!.message;
      }
      return (
        await api.POST("/api/v1/auth/email/confirm", { body: { token: code } })
      ).data!.message;
    });
    setCode("");
    setPassword("");
  }
  return (
    <main id="content" tabIndex={-1} className="auth-page">
      <section className="panel">
        <h1>
          {kind === "verify" ? "Verify your email" : "Reset your password"}
        </h1>
        <p>
          Codes expire shortly and can be used once. Paste the code from your
          email here; never put it in a URL.
        </p>
        <form
          onSubmit={request}
          aria-describedby={error ? "recovery-error" : undefined}
        >
          <label>
            Email address
            <input
              type="email"
              autoComplete="email"
              required
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <button disabled={busy}>Send a new code</button>
        </form>
        <form
          onSubmit={confirm}
          aria-describedby={error ? "recovery-error" : undefined}
        >
          <label>
            Single-use code
            <input
              type="password"
              autoComplete="one-time-code"
              required
              minLength={32}
              maxLength={128}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          {kind === "reset" && (
            <label>
              New password
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          )}
          <button disabled={busy}>
            {kind === "verify" ? "Verify email" : "Change password"}
          </button>
        </form>
        {busy && <p role="status">Please wait…</p>}
        {error && (
          <p id="recovery-error" role="alert" className="error">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}
        <Link to="/login">Back to sign in</Link>
        <p>For demo and educational use with uploaded or simulated data.</p>
      </section>
    </main>
  );
}
