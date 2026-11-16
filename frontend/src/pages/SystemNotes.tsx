import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router";
import { ArrowUpRight } from "lucide-react";
import { PublicCinemaHeader } from "../cinematic/CinemaNav";
import { useSession } from "../lib/session";

const notes = [
  {
    id: "scope",
    title: "Service scope",
    copy: "SubTrack analyzes reviewed statement transactions to identify recurring INR charges. It shows estimated renewals, spending summaries and suggestions for reviewing overlapping subscriptions. It does not initiate transfers, hold funds, or cancel subscriptions on your behalf.",
  },
  {
    id: "import",
    title: "Import lifecycle",
    copy: "In local development you can choose a supported statement, review the mapped or extracted rows, and confirm which rows to import. SubTrack validates and deduplicates them before detecting recurring charges. The dashboard walkthrough shows those stages using sample data.",
  },
  {
    id: "security",
    title: "Security",
    copy: "Workspace access is scoped to the signed-in account or isolated demo session. The assistant uses read-only tools. A server-side check verifies the source of figures in its answers.",
  },
  {
    id: "data",
    title: "Data handling",
    copy: "Your workspace keeps imported transactions and the resulting subscription and alert records. Statement files and PDF passwords are temporary job inputs. Account settings provide export and deletion controls. External AI, when configured, requires consent.",
  },
  {
    id: "limits",
    title: "Operating limits",
    copy: "The hosted demo uses synthetic data and has personal uploads disabled. Renewal dates and missing-payment notices are estimates. Statement import is INR-only and requires review, especially for scanned documents. Live mailbox sync is unavailable.",
  },
  {
    id: "accessibility",
    title: "Accessibility",
    copy: "Use chapter links to move directly through the journey. The object can be turned with arrow keys and reset with Home. You can pause the scene, and a system reduced-motion preference selects still images. All chapters and instructions remain readable when 3D is unavailable.",
  },
] as const;

export default function SystemNotes() {
  const session = useSession();
  const content = useRef<HTMLElement>(null);
  const { hash } = useLocation();
  useEffect(() => {
    const target = notes.find((note) => `#${note.id}` === hash);
    if (target) {
      document.getElementById(target.id)?.scrollIntoView();
    } else {
      window.scrollTo({ top: 0, behavior: "instant" });
      content.current?.focus({ preventScroll: true });
    }
  }, [hash]);
  return (
    <div className="cinema-site cinema-notes cinema-public">
      <a className="skip-link" href="#content">
        Skip to system notes
      </a>
      <PublicCinemaHeader workspace={session ? "/" : "/login"} />
      <main
        id="content"
        className="cinema-notes-body"
        ref={content}
        tabIndex={-1}
      >
        <h1>How SubTrack works</h1>
        <p className="cinema-notes-intro">
          A guide to service scope and data handling.
        </p>
        <div className="cinema-notes-layout">
          <nav aria-label="On this page">
            {notes.map(({ id, title }) => (
              <a key={id} href={`#${id}`}>
                {title}
              </a>
            ))}
          </nav>
          <div>
            {notes.map(({ id, title, copy }) => (
              <section key={id} id={id}>
                <h2>{title}</h2>
                <p>{copy}</p>
              </section>
            ))}
          </div>
        </div>
      </main>
      <footer className="cinema-footer">
        <span>SubTrack</span>
        <Link to="/journey">
          Back to the journey <ArrowUpRight size={14} aria-hidden="true" />
        </Link>
      </footer>
    </div>
  );
}
