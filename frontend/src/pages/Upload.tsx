import { UploadProgress, Warnings } from "../components/UploadProgress";
export { UploadProgress } from "../components/UploadProgress";
import { DemoPanel } from "../components/DemoPanel";
import { ReceiptImport } from "../components/ReceiptImport";
import { StatementReview } from "../components/StatementReview";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { Link } from "react-router";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import { Empty, ErrorState, Heading, Loading } from "../components/Common";
import { useRefresh } from "../hooks/data";
import { useAuthMode } from "../components/AuthMode";
type Preview = components["schemas"]["Preview"];

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
export default function UploadPage() {
  const mode = useAuthMode();
  if (mode.isPending) return <Loading />;
  if (mode.isError)
    return (
      <ErrorState
        error={mode.error}
        retry={() => {
          void mode.refetch();
        }}
      />
    );
  if (mode.data.public_demo_only)
    return (
      <>
        <Heading
          title="Synthetic demo data"
          subtitle="File uploads are disabled on the public demo."
        />
        <p>Public demo — do not upload real statements or personal data.</p>
        <DemoPanel />
      </>
    );
  return (
    <UploadWorkspace receiptsEnabled={!!mode.data.receipt_import_enabled} />
  );
}
function UploadWorkspace({ receiptsEnabled }: { receiptsEnabled: boolean }) {
  const [source, setSource] = useState<"statement" | "receipt">("statement");
  const receiptMode = receiptsEnabled && source === "receipt";
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [layout, setLayout] = useState<Layout>("single");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [statementJobId, setStatementJobId] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const picker = useRef<HTMLInputElement>(null);
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
    if (statementJobId) {
      await api
        .DELETE("/api/v1/uploads/previews/{preview_id}", {
          params: { path: { preview_id: statementJobId } },
        })
        .catch(() => undefined);
      setStatementJobId(null);
    }
    setError("");
    setPreview(null);
    setUploadId(null);
    setFile(null);
    const csv = selected.name.toLowerCase().endsWith(".csv");
    if (!/\.(csv|pdf|jpe?g|png)$/i.test(selected.name)) {
      setError(
        "Choose a CSV, PDF, JPEG or PNG file. Excel is unsupported; export CSV instead.",
      );
      return;
    }
    if (selected.size > (csv ? 5 : 10) * 1024 * 1024) {
      setError(
        csv
          ? "CSV exceeds the 5 MB limit."
          : "PDF/image exceeds the 10 MB limit.",
      );
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.set("file", selected);
      form.set("password", csv ? "" : password);
      setPassword("");
      const result = await api.POST("/api/v1/uploads/preview", {
        body: { file: "", password: csv ? "" : password },
        bodySerializer: () => form,
      });
      setFile(selected);
      if (result.data && "columns" in result.data) {
        setPreview(result.data);
        setMapping(result.data.suggested_mapping);
        setLayout(result.data.suggested_mapping.debit ? "split" : "single");
      } else if (result.data) setStatementJobId(result.data.id);
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
      form.set("edits", "[]");
      const result = await api.POST("/api/v1/uploads", {
        body: { file: "", mapping: "", edits: "[]" },
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
        title={receiptMode ? "Import receipt payments" : "Upload a statement"}
        subtitle={
          receiptMode
            ? "Review synthetic receipt fields before importing them."
            : "Turn transaction history into a clearer recurring spend picture."
        }
      />
      <p>
        <Link to="/mailbox">Open the offline receipt inbox lab</Link>
      </p>
      {receiptsEnabled && (
        <label>
          Import source
          <select
            value={source}
            onChange={(event) => {
              setSource(event.target.value as "statement" | "receipt");
              setPreview(null);
              setStatementJobId(null);
              setUploadId(null);
              setError("");
            }}
          >
            <option value="statement">Bank statement</option>
            <option value="receipt">
              Synthetic email receipt (local only)
            </option>
          </select>
        </label>
      )}
      {receiptMode && (
        <ReceiptImport
          onImported={setUploadId}
          onStart={() => setUploadId(null)}
        />
      )}
      {!receiptMode && (
        <>
          {!statementJobId && !uploadId && <DemoPanel />}
          <div className="steps" aria-label="Upload steps">
            <span
              className={
                !preview && !uploadId && !statementJobId ? "current" : ""
              }
            >
              1 · Choose a file
            </span>
            <span className={preview || statementJobId ? "current" : ""}>
              2 · Check columns
            </span>
            <span className={uploadId ? "current" : ""}>
              3 · Process & review
            </span>
          </div>
          {statementJobId && file && (
            <StatementReview
              key={statementJobId}
              jobId={statementJobId}
              file={file}
              onImported={(id) => {
                setStatementJobId(null);
                setUploadId(id);
              }}
              onCancel={() => {
                setStatementJobId(null);
                picker.current?.focus();
              }}
              onRetry={() => void choose(file)}
            />
          )}
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
              <p>Drop a CSV, PDF, JPEG or PNG here, or choose a file below.</p>
              <label className="file-label">
                Choose statement file
                <input
                  aria-label="Choose statement file"
                  ref={picker}
                  type="file"
                  accept=".csv,.pdf,.jpg,.jpeg,.png,text/csv,application/pdf,image/jpeg,image/png"
                  disabled={busy}
                  onChange={(event) => {
                    void choose(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
              <small>
                CSV: 5 MB / 50,000 rows · PDF: 10 MB / 30 pages · JPEG/PNG: 10
                MB / 25 megapixels · INR only
              </small>
            </div>
            <p className="muted">
              Simple date / description / amount / type exports and Indian bank
              debit / credit layouts are supported. Other currencies are
              rejected by the server for CSV. For extracted statements, verify
              the currency yourself; only INR is supported.
            </p>
            <p className="muted">
              PDF/image extraction runs locally on our server and requires
              review. Use clean English scans around 200 dpi or better. Photos,
              handwriting, heavy skew and blur may be rejected.
            </p>
            <label>
              PDF password (only if encrypted)
              <input
                type="password"
                autoComplete="off"
                value={password}
                maxLength={256}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <small>
              Used in memory only, never stored or logged. Enter it before
              choosing an encrypted PDF, or before retrying.
            </small>
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
                Assign each column once. Preview cells are formula-safe and
                treated as text.
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
        </>
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
      {!receiptMode && upload.data?.status === "failed" && (
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
                {item.source_type === "email_receipt" && (
                  <span className="badge">
                    Email receipt · unverified authenticity
                  </span>
                )}
                <span>{item.row_count} rows</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
