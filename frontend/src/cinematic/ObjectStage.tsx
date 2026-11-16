import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type RefObject,
} from "react";
import { RotateCcw } from "lucide-react";
import { chapters } from "./chapters";
import type { Pose } from "./scene";

type RenderStatus = "loading" | "ready" | "failed";
const neutral = { x: 0, y: 0, dragging: false };

export function ObjectStage({
  progress,
  active,
}: {
  progress: RefObject<number>;
  active: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const pose = useRef<Pose>({ ...neutral });
  const drag = useRef<{ id: number; x: number; y: number } | null>(null);
  const [status, setStatus] = useState<RenderStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const [still, setStill] = useState(
    () =>
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  const [paused, setPaused] = useState(false);
  const descriptiveText = chapters[active].object;
  const staticMode = still || paused;
  const interactive = status === "ready" && !staticMode;

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!media) return;
    const update = () => setStill(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const element = canvas.current;
    if (!element || staticMode) return;
    let active = true;
    let unmount: (() => void) | undefined;
    const dispose = () => {
      drag.current = null;
      pose.current.dragging = false;
      unmount?.();
      unmount = undefined;
    };
    setStatus("loading");
    const fail = () => {
      if (!active) return;
      setStatus("failed");
      queueMicrotask(dispose);
    };
    void import("./scene")
      .then(({ mountScene }) => {
        if (!active) return;
        unmount = mountScene(
          element,
          () => progress.current,
          () => pose.current,
          () => {
            if (active) setStatus("ready");
          },
          fail,
        );
      })
      .catch(fail);
    return () => {
      active = false;
      dispose();
    };
  }, [attempt, progress, staticMode]);

  function rotate(x: number, y: number) {
    const current = pose.current;
    current.x = Math.max(-0.61, Math.min(0.61, current.x + x));
    current.y = Math.max(-1.51, Math.min(1.51, current.y + y));
  }

  function begin(event: PointerEvent<HTMLDivElement>) {
    if (!interactive || event.button !== 0 || drag.current) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.focus({ preventScroll: true });
    pose.current.dragging = true;
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.id !== event.pointerId) return;
    rotate(
      (event.clientY - drag.current.y) * 0.009,
      (event.clientX - drag.current.x) * 0.009,
    );
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
  }

  function end(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.id !== event.pointerId) return;
    drag.current = null;
    pose.current.dragging = false;
  }

  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (!interactive || event.target !== event.currentTarget) return;
    switch (event.key) {
      case "ArrowLeft":
        rotate(0, -0.15);
        break;
      case "ArrowRight":
        rotate(0, 0.15);
        break;
      case "ArrowUp":
        rotate(-0.14, 0);
        break;
      case "ArrowDown":
        rotate(0.14, 0);
        break;
      case "Home":
        pose.current = { ...neutral };
        break;
      default:
        return;
    }
    event.preventDefault();
  }

  return (
    <>
      <div
        className={
          interactive ? "cinema-object is-interactive" : "cinema-object"
        }
        role="group"
        aria-label={descriptiveText}
        aria-describedby="object-controls-description"
        tabIndex={interactive ? 0 : undefined}
        onPointerDown={begin}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        onLostPointerCapture={end}
        onKeyDown={keyboard}
      >
        <div
          className={`cinema-still still-${active}${interactive ? " is-hidden" : ""}`}
          aria-hidden="true"
        />
        {!staticMode && status !== "failed" && (
          <canvas
            key={attempt}
            ref={canvas}
            className={interactive ? "is-rendered" : ""}
            aria-hidden="true"
          />
        )}
      </div>
      <div className="cinema-object-controls">
        <span id="object-controls-description">
          {interactive ? "Drag or use arrow keys to rotate" : "Still view"}
        </span>
        {interactive && (
          <button
            type="button"
            onClick={() => {
              pose.current = { ...neutral };
            }}
            aria-label="Reset object rotation"
          >
            <RotateCcw size={14} aria-hidden="true" /> Reset
          </button>
        )}
        {!still && status === "failed" && !paused ? (
          <button
            type="button"
            onClick={() => {
              setStatus("loading");
              setAttempt((value) => value + 1);
            }}
          >
            Retry 3D
          </button>
        ) : (
          !still && (
            <button type="button" onClick={() => setPaused((value) => !value)}>
              {paused ? "Resume motion" : "Pause motion"}
            </button>
          )
        )}
      </div>
    </>
  );
}
