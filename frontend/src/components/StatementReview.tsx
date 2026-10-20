import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { getToken } from "../lib/session";
import type { components } from "../api/schema";
import { ErrorState, Loading } from "./Common";

type Edit = Pick<components["schemas"]["RowEdit"], "index"> &
  Partial<Omit<components["schemas"]["RowEdit"], "index">>;
type Row = components["schemas"]["ExtractedRow"];
const pageSize = 25;

export function reviewComplete(rows: Row[], edits: Record<number, Edit>) {
  return rows.every((row) => {
    const decision = edits[row.index];
    if (decision?.delete) return true;
    const value = { ...row, ...decision };
    return (
      (!row.flags.length || decision?.verified === true) &&
      !!value.date &&
      !!(value.description || "").trim() &&
      !!value.amount &&
      /^\d{1,10}(?:\.\d{1,2})?$/.test(value.amount) &&
      !!value.type
    );
  });
}

export function StatementReview({
  jobId,
  file,
  onImported,
  onCancel,
  onRetry,
}: {
  jobId: string;
  file: File;
  onImported: (id: string) => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const cache = useQueryClient();
  const completed = useRef(false);
  const lifecycle = useRef({ generation: 0, jobId });
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const query = useQuery({
    queryKey: ["statement-preview", jobId],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/uploads/previews/{preview_id}", {
          signal,
          params: { path: { preview_id: jobId } },
        })
      ).data!,
    refetchInterval: (q) =>
      ["pending", "processing"].includes(q.state.data?.status || "pending")
        ? Math.min(1000 * 2 ** Math.min(q.state.dataUpdateCount, 2), 4000)
        : false,
    retry: false,
  });
  useEffect(() => {
    const local = URL.createObjectURL(file);
    setUrl(local);
    return () => URL.revokeObjectURL(local);
  }, [file]);
  useEffect(() => {
    const activeLifecycle = lifecycle.current;
    const generation = ++activeLifecycle.generation;
    activeLifecycle.jobId = jobId;
    return () => {
      // Strict Mode replays setup/cleanup synchronously. Only a real unmount (or a
      // different job) should cancel; do not delete a live job during the replay.
      queueMicrotask(() => {
        if (
          activeLifecycle.generation !== generation &&
          activeLifecycle.jobId === jobId
        )
          return;
        if (!completed.current && getToken()) {
          void api
            .DELETE("/api/v1/uploads/previews/{preview_id}", {
              params: { path: { preview_id: jobId } },
            })
            .catch(() => undefined);
        }
        cache.removeQueries({ queryKey: ["statement-preview", jobId] });
      });
    };
  }, [cache, jobId]);
  function change(index: number, value: Partial<Edit>) {
    setEdits((current) => ({
      ...current,
      [index]: { ...current[index], index, verified: false, ...value },
    }));
  }
  async function cancel() {
    setBusy(true);
    try {
      await api.DELETE("/api/v1/uploads/previews/{preview_id}", {
        params: { path: { preview_id: jobId } },
      });
      completed.current = true;
      onCancel();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.set("preview_id", jobId);
      form.set("edits", JSON.stringify(Object.values(edits)));
      const response = await api.POST("/api/v1/uploads", {
        body: {
          preview_id: jobId,
          edits: JSON.stringify(Object.values(edits)),
        },
        bodySerializer: () => form,
      });
      completed.current = true;
      onImported(response.data!.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  if (query.isPending) return <Loading text="Opening statement preview…" />;
  const job = query.data;
  if (job.status === "failed")
    return (
      <section className="panel" aria-label="Statement preview failure">
        <h2>Statement preview failed</h2>
        <p role="alert">
          {job.error_message || "Re-export the statement or try CSV."}
        </p>
        {(job.error_code === "password_required" ||
          job.error_code === "wrong_password") && (
          <p>
            Enter the PDF password in the field below, then retry. It is never
            stored.
          </p>
        )}
        <button onClick={onRetry}>Retry local file preview</button>
        <button onClick={() => void cancel()} disabled={busy}>
          Cancel preview
        </button>
        {error && <ErrorState error={new Error(error)} />}
      </section>
    );
  if (job.status === "cancelled")
    return (
      <p role="status">Preview cancelled. Choose a file to begin again.</p>
    );
  if (!job.result)
    return (
      <section className="panel" aria-label="Statement extraction progress">
        <h2>Extracting statement locally</h2>
        <div role="status" aria-live="polite">
          <p>Stage: {job.stage.replaceAll("_", " ")}</p>
          <progress
            aria-label="Pages extracted"
            max={job.total_pages || 1}
            value={job.processed_pages}
          />
          <p>
            {job.processed_pages} / {job.total_pages} pages extracted
          </p>
        </div>
        <button disabled={busy} onClick={() => void cancel()}>
          Cancel preview
        </button>
        {error && <ErrorState error={new Error(error)} />}
      </section>
    );
  const result = job.result;
  const rows = result.rows.filter(
    (row) =>
      !flaggedOnly ||
      (row.flags.length > 0 &&
        !reviewComplete([row], edits) &&
        !edits[row.index]?.delete),
  );
  const visible = rows.slice(page * pageSize, (page + 1) * pageSize);
  const canReviewAll = result.rows.every((row) => {
    const value = { ...row, ...edits[row.index] };
    return (
      edits[row.index]?.delete ||
      (!!value.date &&
        !!value.amount &&
        !!value.type &&
        !!(value.description || "").trim())
    );
  });
  return (
    <section className="panel statement-review" aria-labelledby="review-title">
      <h2 id="review-title">Review every extracted row</h2>
      <p role="status">Extraction ready. Review all values before import.</p>
      <p className="notice-box">
        OCR can misread digits. Compare dates, descriptions, amounts and
        debit/credit types with your local copy. You are responsible for
        verifying flagged values before import. All imports are INR only.
      </p>
      <p>
        Source: {result.source_type.replaceAll("_", " ")} · Pages:{" "}
        {result.page_count} · Flagged rows: {result.flagged_count}
      </p>
      <p className="notice-box">
        Reconciliation: <strong>{result.reconciliation.status}</strong> ·
        Balance checks: {result.reconciliation.balance_checks} · Total checks:{" "}
        {result.reconciliation.total_checks}. Matched balances do not prove
        every field correct.
      </p>
      {result.warnings.map((warning) => (
        <p key={warning}>{warning}</p>
      ))}
      <p className="muted">
        Preview expires: {job.expires_at}. Originals are not retained. This
        preview uses only your browser’s local file.
      </p>
      <p className="muted">
        Recognition scores are not transaction accuracy. Descriptions are plain
        text; formula prefixes are neutralized in this preview. Extracted
        descriptions retain their original text unless you edit them.
      </p>
      <div className="statement-review-layout">
        <details className="local-statement">
          <summary>Show my local file</summary>
          {file.name.toLowerCase().endsWith(".pdf") ? (
            <>
              <iframe
                src={url}
                title="Local PDF statement preview"
                sandbox=""
              />
              <p>
                If the browser blocks the embedded viewer, open the local copy
                in your PDF viewer.
              </p>
              <a href={url} target="_blank" rel="noreferrer">
                Open local PDF copy
              </a>
            </>
          ) : (
            <img src={url} alt="Local statement file for comparison" />
          )}
        </details>
        <div className="review-controls">
          <div className="review-toolbar">
            <label>
              <input
                type="checkbox"
                checked={flaggedOnly}
                onChange={(event) => {
                  setFlaggedOnly(event.target.checked);
                  setPage(0);
                }}
              />
              Show only unverified flagged rows
            </label>
            <button
              disabled={busy || !canReviewAll}
              onClick={() =>
                setEdits((current) =>
                  Object.fromEntries(
                    result.rows.map((row) => [
                      row.index,
                      {
                        ...current[row.index],
                        index: row.index,
                        verified: true,
                      },
                    ]),
                  ),
                )
              }
            >
              I reviewed every extracted row
            </button>
          </div>
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Extracted statement rows"
          >
            <table>
              <caption>
                Extracted rows — edit incorrect values, verify, or remove
              </caption>
              <thead>
                <tr>
                  {[
                    "Row / page",
                    "Date",
                    "Description",
                    "Amount (INR)",
                    "Type",
                    "Confidence / notices",
                    "Review",
                  ].map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  const value = { ...row, ...edits[row.index] };
                  const n = row.index + 1;
                  return (
                    <tr key={row.index}>
                      <th scope="row">
                        Row {n}
                        <br />
                        Page {row.page}
                      </th>
                      {value.delete ? (
                        <td colSpan={6}>
                          Removed from this import.{" "}
                          <button
                            onClick={() => change(row.index, { delete: false })}
                          >
                            Undo remove row {n}
                          </button>
                        </td>
                      ) : (
                        <>
                          <td>
                            <input
                              aria-label={`Row ${n} date`}
                              aria-describedby={`review-notices-${n}`}
                              aria-invalid={!value.date}
                              type="date"
                              value={value.date || ""}
                              onChange={(event) =>
                                change(row.index, { date: event.target.value })
                              }
                            />
                          </td>
                          <td>
                            <input
                              aria-label={`Row ${n} description`}
                              aria-describedby={`review-notices-${n}`}
                              aria-invalid={!(value.description || "").trim()}
                              value={value.description || ""}
                              maxLength={1000}
                              onChange={(event) =>
                                change(row.index, {
                                  description: event.target.value,
                                })
                              }
                            />
                          </td>
                          <td>
                            <input
                              aria-label={`Row ${n} amount`}
                              aria-describedby={`review-notices-${n}`}
                              aria-invalid={
                                !/^\d{1,10}(?:\.\d{1,2})?$/.test(
                                  value.amount || "",
                                )
                              }
                              inputMode="decimal"
                              value={value.amount || ""}
                              onChange={(event) =>
                                change(row.index, {
                                  amount: event.target.value,
                                })
                              }
                            />
                          </td>
                          <td>
                            <select
                              aria-label={`Row ${n} type`}
                              aria-describedby={`review-notices-${n}`}
                              aria-invalid={!value.type}
                              value={value.type || ""}
                              onChange={(event) =>
                                change(row.index, {
                                  type: event.target.value as
                                    "debit" | "credit",
                                })
                              }
                            >
                              <option value="">Choose type</option>
                              <option value="debit">Debit</option>
                              <option value="credit">Credit</option>
                            </select>
                          </td>
                          <td>
                            <span className="badge">
                              Confidence {row.confidence}%
                            </span>
                            <ul id={`review-notices-${n}`}>
                              {row.flags.map((flag) => (
                                <li key={flag}>{flag}</li>
                              ))}
                            </ul>
                          </td>
                          <td>
                            <label>
                              <input
                                type="checkbox"
                                aria-label={`Verify row ${n}`}
                                checked={!!value.verified}
                                onChange={(event) =>
                                  change(row.index, {
                                    verified: event.target.checked,
                                  })
                                }
                              />
                              Reviewed
                            </label>
                            <button
                              onClick={() =>
                                change(row.index, { delete: true })
                              }
                            >
                              Remove row {n}
                            </button>
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!visible.length && (
              <p>
                No rows in this view. Show all rows or choose the previous page.
              </p>
            )}
          </div>
          <div className="review-toolbar">
            <button
              disabled={page === 0}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous rows
            </button>
            <button
              disabled={(page + 1) * pageSize >= rows.length}
              onClick={() => setPage((current) => current + 1)}
            >
              Next rows
            </button>
            <button
              className="primary"
              disabled={busy || !reviewComplete(result.rows, edits)}
              onClick={() => void confirm()}
            >
              Import reviewed rows
            </button>
            <button disabled={busy} onClick={() => void cancel()}>
              Cancel preview
            </button>
          </div>
        </div>
      </div>
      {busy && <p role="status">Submitting your reviewed rows…</p>}
      {error && <ErrorState error={new Error(error)} />}
    </section>
  );
}
