import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";

export function CinemaNav({ workspace = "/login" }: { workspace?: string }) {
  return (
    <nav className="cinema-nav" aria-label="SubTrack">
      <Link className="cinema-wordmark" to="/journey">
        SubTrack
      </Link>
      <div className="cinema-nav-links">
        <Link to="/journey">Journey</Link>
        <Link to="/system-notes">System notes</Link>
      </div>
      <Link className="cinema-ghost" to={workspace}>
        Open workspace <ArrowUpRight size={16} aria-hidden="true" />
      </Link>
    </nav>
  );
}

export function PublicCinemaHeader({ workspace }: { workspace: string }) {
  return (
    <header className="cinema-header">
      <CinemaNav workspace={workspace} />
      <p className="cinema-demo-notice">
        Public demo — do not upload real statements or personal data
      </p>
    </header>
  );
}
