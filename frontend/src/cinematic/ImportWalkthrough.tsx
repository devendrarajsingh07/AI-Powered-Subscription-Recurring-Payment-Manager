import { useEffect, useState } from "react";
import { Check, Layers3, RotateCcw } from "lucide-react";

const steps = [
  ["Choose file", "Select a supported statement."],
  ["Review", "Check the rows and choose what to import."],
  ["Validate", "Check dates, amounts and duplicates."],
  ["Detect", "Look for recurring charges."],
  ["Record", "Save reviewed transactions and their recurring matches."],
  ["Ready", "Review the results in the workspace."],
] as const;

export function ImportWalkthrough() {
  const [stage, setStage] = useState(-1);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (stage === steps.length - 1) setPlaying(false);
      else setStage(stage + 1);
    }, 680);
    return () => window.clearTimeout(timer);
  }, [playing, stage]);

  function replay() {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setStage(steps.length - 1);
      setPlaying(false);
    } else {
      setStage(0);
      setPlaying(true);
    }
  }
  return (
    <section
      className="panel import-walkthrough"
      aria-labelledby="import-walkthrough-title"
    >
      <div className="section-heading">
        <div>
          <h2 id="import-walkthrough-title">
            <Layers3 size={19} aria-hidden="true" /> Import walkthrough
          </h2>
          <p className="muted">Simulation · No statement is imported.</p>
        </div>
        {playing ? (
          <button type="button" onClick={() => setPlaying(false)}>
            Stop walkthrough
          </button>
        ) : (
          <button type="button" onClick={replay}>
            <RotateCcw size={16} aria-hidden="true" /> Replay walkthrough
          </button>
        )}
      </div>
      <ol className="import-pipeline">
        {steps.map(([label, description], index) => (
          <li
            key={label}
            data-step={
              index < stage
                ? "complete"
                : index === stage
                  ? "active"
                  : "waiting"
            }
            aria-current={index === stage ? "step" : undefined}
          >
            <span className="pipeline-node" aria-hidden="true">
              {index < stage ? <Check size={14} /> : index + 1}
            </span>
            <span>{label}</span>
            <span className="sr-only">. {description}</span>
          </li>
        ))}
      </ol>
      <p role="status" className="pipeline-status">
        {stage === -1
          ? "Preview how a reviewed statement becomes a recurring-spend summary."
          : steps[stage][1]}
      </p>
    </section>
  );
}
