import { Link } from "react-router";
import { CheckCircle2 } from "lucide-react";
import type { components } from "../api/schema";
type Upload = components["schemas"]["UploadOut"];
export function UploadProgress({ upload }: { upload: Upload }) {
  return (
    <section className="panel" aria-label="Upload progress">
      <div className="section-heading">
        <h2>
          {upload.status === "done"
            ? upload.source_type === "email_receipt"
              ? "Receipt processed"
              : "Statement processed"
            : upload.status === "failed"
              ? "Upload failed"
              : upload.source_type === "email_receipt"
                ? "Processing your receipt"
                : "Processing your statement"}
        </h2>
        <span className="badge">{upload.status}</span>
      </div>
      <div role="status" aria-live="polite">
        <p>
          Stage: <strong>{upload.stage.replaceAll("_", " ")}</strong>
        </p>
        <progress
          max={upload.total_rows || 1}
          value={upload.processed_rows}
          aria-label="Rows processed"
        />
        <p>
          {upload.processed_rows} / {upload.total_rows} rows processed
        </p>
      </div>
      {upload.status === "failed" && (
        <p role="alert" className="error">
          {upload.error_message ||
            "Processing failed. Please retry your upload."}
        </p>
      )}
      {upload.status === "done" && (
        <>
          <div className="result-grid">
            <div>
              <strong>{upload.inserted_count}</strong>
              <span>Inserted</span>
            </div>
            <div>
              <strong>{upload.duplicate_count}</strong>
              <span>Duplicates skipped</span>
            </div>
            <div>
              <strong>{upload.malformed_count}</strong>
              <span>Malformed rows</span>
            </div>
            <div>
              <strong>{upload.detected_count}</strong>
              <span>Detected products</span>
            </div>
            {upload.source_type !== "csv" && (
              <div>
                <strong>{upload.excluded_count}</strong>
                <span>Excluded from review</span>
              </div>
            )}
          </div>
          <p className="success">
            <CheckCircle2 size={18} />
            Your subscription view is ready.
          </p>
          <Link className="button primary" to="/">
            View dashboard
          </Link>{" "}
          <Link className="button" to="/subscriptions">
            View subscriptions
          </Link>
        </>
      )}
      {upload.warnings.length > 0 && <Warnings warnings={upload.warnings} />}
      {upload.malformed_count > 0 && (
        <p className="notice-box">{upload.remainder_notice}</p>
      )}
    </section>
  );
}
export function Warnings({
  warnings,
}: {
  warnings: components["schemas"]["RowWarning"][];
}) {
  return (
    <details open>
      <summary>Row warnings ({warnings.length} shown)</summary>
      <ul>
        {warnings.map((warning, index) => (
          <li key={index}>
            Line {warning.line}: {warning.reason}
          </li>
        ))}
      </ul>
    </details>
  );
}
