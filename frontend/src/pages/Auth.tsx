import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { api, ApiError, errorMessage } from "../api/client";
import { getSignOutNotice, saveSession, useSession } from "../lib/session";
export function passwordError(
  password: string,
  register: boolean,
): string | null {
  if (new TextEncoder().encode(password).length > 72)
    return "Use at most 72 UTF-8 bytes.";
  if (!password) return "Enter your password.";
  if (
    register &&
    (Array.from(password).length < 12 ||
      [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter((pattern) =>
        pattern.test(password),
      ).length < 3)
  )
    return "Use 12 or more characters with at least three of: lowercase, uppercase, numbers and symbols.";
  return null;
}
export function Auth({ register = false }: { register?: boolean }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const state = {
    ...getSignOutNotice(),
    ...(location.state as {
      from?: string;
      message?: string;
      deleted?: Record<string, number>;
    } | null),
  };
  const destination =
    state?.from?.startsWith("/") &&
    !state.from.startsWith("//") &&
    !["/login", "/register"].includes(state.from)
      ? state.from
      : "/";
  if (session) return <Navigate to={destination} replace />;
  async function submit(event: FormEvent) {
    event.preventDefault();
    const invalid = passwordError(password, register);
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = { email: email.trim().toLowerCase(), password };
      if (register) await api.POST("/api/v1/auth/register", { body });
      const result = await api.POST("/api/v1/auth/login", { body });
      saveSession(result.data!);
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 401
          ? "Unable to sign in. Check your email and password."
          : caught instanceof ApiError && caught.status === 409
            ? "Unable to create an account with these details. Try signing in."
            : errorMessage(caught),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="content" tabIndex={-1} className="auth-page">
      <section className="auth-story">
        <Link className="brand" to="/login">
          SubTrack<span className="brand-dot">.</span>
        </Link>
        <div>
          <span className="eyebrow">A LITTLE CLARITY, EVERY MONTH</span>
          <h1>
            Keep track.
            <br />
            Stay a step ahead.
          </h1>
          <p>
            A clear view of your subscriptions, recurring bills and the renewals
            around the corner.
          </p>
          <div className="auth-proof">
            <ShieldCheck size={20} />
            <span>CSV uploads. Your data, your control.</span>
          </div>
        </div>
        <p className="notice">
          For demo and educational use with uploaded or simulated data.
        </p>
      </section>
      <section className="auth-panel">
        <div className="auth-form">
          <span className="eyebrow">WELCOME TO SUBTRACK</span>
          <h2>{register ? "Create your account" : "Good to see you"}</h2>
          <p>
            {register
              ? "Start with a statement. Get a clearer picture."
              : "Sign in to your recurring spend workspace."}
          </p>
          {state?.message && (
            <p role="status" className="success">
              {state.message}
            </p>
          )}
          {state?.deleted && (
            <details open>
              <summary>Deleted data counts</summary>
              <dl className="definition-list">
                {Object.entries(state.deleted).map(([name, count]) => (
                  <div key={name}>
                    <dt>{name.replaceAll("_", " ")}</dt>
                    <dd>{count}</dd>
                  </div>
                ))}
              </dl>
            </details>
          )}
          <form
            onSubmit={submit}
            aria-describedby={error ? "auth-error" : undefined}
          >
            <label>
              Email address
              <input
                type="email"
                autoComplete="email"
                required
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                required
                minLength={register ? 12 : 1}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-describedby={register ? "password-help" : undefined}
              />
            </label>
            {register && (
              <small id="password-help">
                At least 12 characters, with three of: lowercase, uppercase,
                numbers and symbols. Maximum 72 UTF-8 bytes.
              </small>
            )}
            {error && (
              <p id="auth-error" role="alert" className="error">
                {error}
              </p>
            )}
            <button className="primary full" disabled={busy}>
              {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="auth-switch">
            {register ? "Already have an account?" : "New here?"}{" "}
            <Link
              to={register ? "/login" : "/register"}
              state={{ from: state?.from }}
            >
              {register ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
