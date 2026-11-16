import { useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { Link, useLocation } from "react-router";
import { chapters } from "../cinematic/chapters";
import { PublicCinemaHeader } from "../cinematic/CinemaNav";
import { ObjectStage } from "../cinematic/ObjectStage";
import { useSession } from "../lib/session";

export default function Journey() {
  const session = useSession();
  const hash = useLocation().hash;
  const workspace = session ? "/" : "/login";
  const sections = useRef<(HTMLElement | null)[]>([]);
  const content = useRef<HTMLElement>(null);
  const progress = useRef(0);
  const [active, setActive] = useState(0);

  useEffect(() => {
    let frame = 0;
    function update() {
      frame = 0;
      const bounds = sections.current.map((section) =>
        section?.getBoundingClientRect(),
      );
      const guide = window.innerHeight * 0.52;
      let value = chapters.length - 1;
      for (let i = 0; i < chapters.length; i++) {
        const current = bounds[i];
        const next = bounds[i + 1];
        if (!current) continue;
        if (current.top + current.height * 0.52 >= guide) {
          value = i;
          break;
        }
        if (next && next.top + next.height * 0.52 > guide) {
          const origin = current.top + current.height * 0.52;
          const target = next.top + next.height * 0.52;
          value = i + (guide - origin) / (target - origin);
          break;
        }
      }
      progress.current = value;
      setActive(Math.round(value));
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    const target = chapters.find((chapter) => `#${chapter.id}` === hash);
    if (target) {
      document.getElementById(target.id)?.scrollIntoView();
    } else {
      window.scrollTo({ top: 0, behavior: "instant" });
      content.current?.focus({ preventScroll: true });
    }
  }, [hash]);

  return (
    <div className="cinema-site cinema-public">
      <a className="skip-link" href="#the-idea">
        Skip to the journey
      </a>
      <PublicCinemaHeader workspace={workspace} />
      <main className="cinema-journey" id="content" ref={content} tabIndex={-1}>
        <div className="cinema-stage">
          <div className="cinema-stage-inner">
            <ObjectStage progress={progress} active={active} />
          </div>
        </div>
        <div className="cinema-chapters">
          {chapters.map((chapter, index) => {
            const Title = index === 0 ? "h1" : "h2";
            return (
              <section
                className="cinema-chapter"
                id={chapter.id}
                key={chapter.id}
                ref={(element) => {
                  sections.current[index] = element;
                }}
              >
                <div className="cinema-chapter-copy">
                  {index > 0 && (
                    <p className="cinema-chapter-name">{chapter.label}</p>
                  )}
                  <Title>
                    {chapter.headline}
                    <em>{chapter.emphasis}</em>
                  </Title>
                  <p className="cinema-copy">{chapter.copy}</p>
                  {(index === 0 || index === chapters.length - 1) && (
                    <>
                      <Link className="cinema-primary" to={workspace}>
                        {index === 0 ? "Explore the demo" : "Open workspace"}{" "}
                        <ArrowRight size={18} aria-hidden="true" />
                      </Link>
                    </>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </main>
      <div className="cinema-chapter-dock">
        <nav aria-label="Journey chapters" className="cinema-chapter-nav">
          {chapters.map((chapter, index) => (
            <a
              key={chapter.id}
              href={`#${chapter.id}`}
              aria-current={index === active ? "location" : undefined}
            >
              <span aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span>{chapter.label}</span>
            </a>
          ))}
        </nav>
      </div>
      <footer className="cinema-footer">
        <span>SubTrack</span>
        <p>Recurring spending analysis. Public demo uses synthetic data.</p>
        <Link to="/system-notes">System notes</Link>
      </footer>
    </div>
  );
}
