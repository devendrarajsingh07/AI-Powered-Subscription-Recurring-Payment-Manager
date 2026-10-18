import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { CheckCircle2, FileUp } from "lucide-react";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import { Empty, ErrorState, Heading, Loading } from "../components/Common";
import { useRefresh } from "../hooks/data";
type Preview = components["schemas"]["Preview"];
type Upload = components["schemas"]["UploadOut"];
export type Layout = "single" | "split";
export function mappingForLayout(
  mapping: Record<string, string>,
  layout: Layout,
) {
  return Object.fromEntries(
    Object.entries(mapping).filter(
      ([key, value]) =>
        !!value &&
        !(
          layout === "single" ? ["debit", "credit"] : ["amount", "type"]
        ).includes(key),
    ),
  );
}
export function mappingValid(mapping: Record<string, string>, layout: Layout) {
  const required =
    layout === "single"
      ? ["date", "description", "amount", "type"]
      : ["date", "description", "debit", "credit"];
  const selected = Object.values(mappingForLayout(mapping, layout));
  return (
    required.every((key) => !!mapping[key]) &&
    new Set(selected).size === selected.length
  );
}
export function UploadProgress({ upload }: { upload: Upload }) {
  return (
    <section className="panel" aria-label="Upload progress">
      <div className="section-heading">
        <h2>
          {upload.status === "done"
            ? "Statement processed"
            : upload.status === "failed"
              ? "Upload failed"
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
function Warnings({
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
export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [layout, setLayout] = useState<Layout>("single");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uploadId, setUploadId] = useState<string | null>(null);
  const refresh = useRefresh();
  const upload = useQuery({
    queryKey: ["upload", uploadId],
    enabled: !!uploadId,
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/uploads/{upload_id}", {
          signal,
          params: { path: { upload_id: uploadId! } },
        })
      ).data!,
    refetchInterval: (query) => {
      const value = query.state.data;
      return value?.status === "done" || value?.status === "failed"
        ? false
        : Math.min(1000 * 2 ** Math.min(query.state.dataUpdateCount, 3), 5000);
    },
  });
  const history = useQuery({
    queryKey: ["uploads"],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/uploads", {
          signal,
          params: { query: { limit: 10 } },
        })
      ).data!,
  });
  useEffect(() => {
    if (upload.data?.status === "done") void refresh();
  }, [upload.data?.status, refresh]);
  async function choose(selected?: File) {
    if (!selected) return;
    setError("");
    setPreview(null);
    setUploadId(null);
    setFile(null);
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file.");
      return;
    }
    if (selected.size > 5 * 1024 * 1024) {
      setError("CSV exceeds the 5 MB limit.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.set("file", selected);
      const result = await api.POST("/api/v1/uploads/preview", {
        body: { file: "" },
        bodySerializer: () => form,
      });
      setFile(selected);
      setPreview(result.data!);
      setMapping(result.data!.suggested_mapping);
      setLayout(result.data!.suggested_mapping.debit ? "split" : "single");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!file || !mappingValid(mapping, layout)) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("mapping", JSON.stringify(mappingForLayout(mapping, layout)));
      const result = await api.POST("/api/v1/uploads", {
        body: { file: "", mapping: "" },
        bodySerializer: () => form,
      });
      setUploadId(result.data!.id);
      setPreview(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Upload a statement"
        subtitle="Turn transaction history into a clearer recurring spend picture."
      />
      <div className="steps" aria-label="Upload steps">
        <span className={!preview && !uploadId ? "current" : ""}>
          1 · Choose CSV
        </span>
        <span className={preview ? "current" : ""}>2 · Check columns</span>
        <span className={uploadId ? "current" : ""}>3 · Process & review</span>
      </div>
      <section className="panel">
        <div
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            if (!busy) void choose(event.dataTransfer.files[0]);
          }}
        >
          <FileUp size={36} />
          <h2>Start with your transaction history</h2>
          <p>Drop a CSV here, or choose a file below.</p>
          <label className="file-label">
            Choose CSV file
            <input
              aria-label="Choose CSV file"
              type="file"
              accept=".csv,text/csv"
              disabled={busy}
              onChange={(event) => {
                void choose(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
          </label>
          <small>Up to 5 MB and 50,000 rows · UTF-8 · INR only</small>
        </div>
        <p className="muted">
          Simple date / description / amount / type exports and Indian bank
          debit / credit layouts are supported. Other currencies are rejected by
          the server.
        </p>
      </section>
      {error && <ErrorState error={new Error(error)} />}
      {busy && <Loading text="Reading your statement…" />}
      {preview && (
        <section className="panel">
          <h2>Check your column mapping</h2>
          <p>
            {file?.name} · {preview.row_count} rows · Delimiter:{" "}
            {preview.delimiter === "\t" ? "Tab" : preview.delimiter} · Date
            formats:{" "}
            {preview.date_formats.join(", ") ||
              "Choose the correct date column"}
          </p>
          <label>
            Amount layout
            <select
              value={layout}
              onChange={(event) => setLayout(event.target.value as Layout)}
            >
              <option value="single">Single amount + type</option>
              <option value="split">Separate debit / credit</option>
            </select>
          </label>
          <div className="mapping-grid">
            {[
              "date",
              "description",
              ...(layout === "single"
                ? ["amount", "type"]
                : ["debit", "credit"]),
              "currency",
            ].map((field) => (
              <label key={field}>
                {field === "currency"
                  ? "Currency (optional)"
                  : field[0].toUpperCase() + field.slice(1)}
                <select
                  aria-label={`Map ${field}`}
                  value={mapping[field] || ""}
                  onChange={(event) =>
                    setMapping({ ...mapping, [field]: event.target.value })
                  }
                >
                  <option value="">
                    {field === "currency" ? "Assume INR" : "Choose column"}
                  </option>
                  {preview.columns.map((column) => (
                    <option key={column}>{column}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <p className="muted">
            Assign each column once. Preview cells are formula-safe and treated
            as text.
          </p>
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Scrollable data table"
          >
            <table>
              <caption>Statement preview</caption>
              <thead>
                <tr>
                  {preview.columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.warnings.length > 0 && (
            <Warnings warnings={preview.warnings} />
          )}
          {preview.malformed_csv && (
            <p className="notice-box">{preview.remainder_notice}</p>
          )}
          <button
            className="primary"
            disabled={busy || !mappingValid(mapping, layout)}
            onClick={() => {
              void confirm();
            }}
          >
            Confirm and import
          </button>
        </section>
      )}
      {uploadId &&
        (upload.isError ? (
          <ErrorState
            error={upload.error}
            retry={() => {
              void upload.refetch();
            }}
          />
        ) : upload.data ? (
          <UploadProgress upload={upload.data} />
        ) : (
          <Loading text="Waiting for upload progress…" />
        ))}
      {upload.data?.status === "failed" && (
        <button
          onClick={() => {
            setUploadId(null);
            if (file) void choose(file);
          }}
        >
          Retry upload
        </button>
      )}
      <section className="panel">
        <h2>Recent uploads</h2>
        <p className="muted">
          You can leave this page while processing. Open an upload below to
          check its real status.
        </p>
        {history.isPending ? (
          <Loading />
        ) : history.isError ? (
          <ErrorState
            error={history.error}
            retry={() => {
              void history.refetch();
            }}
          />
        ) : !history.data.items.length ? (
          <Empty>Your uploaded statements will appear here.</Empty>
        ) : (
          <ul className="upload-history">
            {history.data.items.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => {
                    setPreview(null);
                    setUploadId(item.id);
                  }}
                >
                  {item.filename}
                </button>
                <span className="badge">{item.status}</span>
                <span>{item.row_count} rows</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
