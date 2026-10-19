import {
  Component,
  Suspense,
  lazy,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router";
import {
  CalendarDays,
  CreditCard,
  House,
  Lightbulb,
  LogOut,
  Menu,
  Moon,
  Settings,
  Sun,
  Tags,
  Upload,
} from "lucide-react";
import { api } from "./api/client";
import { clearSession, getSignOutNotice, useSession } from "./lib/session";
import { ErrorState, Loading } from "./components/Common";
import { Auth } from "./pages/Auth";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const UploadPage = lazy(() => import("./pages/Upload"));
const Subscriptions = lazy(() => import("./pages/Subscriptions"));
const Renewals = lazy(() => import("./pages/Renewals"));
const Categories = lazy(() => import("./pages/Categories"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="fatal">
        <h1>Something went wrong</h1>
        <p>Your data is still saved on the server.</p>
        <button onClick={() => window.location.reload()}>
          Reload SubTrack
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
const navigation = [
  ["/", "Overview", House],
  ["/upload", "Upload statement", Upload],
  ["/subscriptions", "Subscriptions", CreditCard],
  ["/renewals", "Renewals", CalendarDays],
  ["/recommendations", "Recommendations", Lightbulb],
  ["/categories", "Categories", Tags],
  ["/settings", "Settings", Settings],
] as const;
function Shell() {
  const session = useSession();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("subtrack.theme") === "dark",
  );
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/auth/me", { signal })).data!,
    enabled: !!session,
  });
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("subtrack.theme", dark ? "dark" : "light");
  }, [dark]);
  if (!session)
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <header className="mobile-bar">
        <span className="brand">
          SubTrack<span className="brand-dot">.</span>
        </span>
        <button
          aria-label="Toggle navigation"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <Menu />
        </button>
      </header>
      <aside className={open ? "sidebar open" : "sidebar"}>
        <a className="brand" href="/">
          SubTrack<span className="brand-dot">.</span>
        </a>
        <span className="nav-label">YOUR WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(([path, title, Icon]) => (
            <NavLink
              end={path === "/"}
              key={path}
              to={path}
              onClick={() => setOpen(false)}
            >
              <Icon size={19} />
              {title}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="notice">
            For demo and educational use with uploaded or simulated data.
          </p>
          <div className="user-email">{me.data?.email || "Your account"}</div>
          <div className="user-actions">
            <button onClick={() => clearSession()}>
              <LogOut size={17} />
              Log out
            </button>
            <button
              className="icon-button"
              aria-label={dark ? "Use light theme" : "Use dark theme"}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </div>
      </aside>
      <main id="content" tabIndex={-1}>
        {me.isError && (
          <ErrorState
            error={me.error}
            retry={() => {
              void me.refetch();
            }}
          />
        )}
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
        <footer>
          SubTrack · For demo and educational use with uploaded or simulated
          data.
        </footer>
      </main>
    </div>
  );
}
export function App() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const session = useSession();
  useEffect(() => {
    const onLogout = (event: Event) => {
      const expired = (event as CustomEvent<{ expired: boolean }>).detail
        .expired;
      void client.cancelQueries();
      client.clear();
      navigate("/login", {
        replace: true,
        state: {
          message: expired
            ? "Your session expired. Please sign in again."
            : getSignOutNotice()?.message || "You have been signed out.",
          deleted: getSignOutNotice()?.deleted,
          from: location.pathname + location.search,
        },
      });
    };
    window.addEventListener("subtrack:logout", onLogout);
    return () => window.removeEventListener("subtrack:logout", onLogout);
  }, [client, navigate, location.pathname, location.search]);
  useEffect(() => {
    if (!session) return;
    const timeout = window.setTimeout(
      () => clearSession(true),
      Math.max(0, session.expires - Date.now()),
    );
    return () => clearTimeout(timeout);
  }, [session]);
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/register" element={<Auth register />} />
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="subscriptions" element={<Subscriptions />} />
          <Route path="renewals" element={<Renewals />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="categories" element={<Categories />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route
            path="*"
            element={
              <>
                <h1>Page not found</h1>
                <NavLink to="/">Back to overview</NavLink>
              </>
            }
          />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
