import { useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import { ErrorState, Loading } from "./Common";
import { StatementReview } from "./StatementReview";

export function ReceiptImport({
  onImported,
  onStart,
}: {
  onImported: (id: string) => void;
  onStart?: () => void;
}) {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const picker = useRef<HTMLInputElement>(null);

  async function choose(selected?: File) {
    if (!selected || busy || previewId) return;
    setError("");
    if (!selected.name.toLowerCase().endsWith(".eml")) {
      setError(
        "Choose a synthetic .eml receipt. Mailbox connections are not available.",
      );
      return;
    }
    if (selected.size > 1024 * 1024) {
      setError("EML receipt exceeds the 1 MB limit.");
      return;
    }
    setBusy(true);
    onStart?.();
    try {
      const form = new FormData();
      form.set("file", selected);
      const response = await api.POST("/api/v1/receipts/preview", {
        body: { file: "" },
        bodySerializer: () => form,
      });
      setFile(selected);
      setPreviewId(response.data!.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="receipt-import-title">
      <div className="panel">
        <h2 id="receipt-import-title">Synthetic email receipts</h2>
        <p className="notice-box">
          Local development only. Use synthetic fixtures, never personal emails.
          Gmail is not connected. No email content is sent to an AI provider.
        </p>
        <p>
          Use a separate empty account: receipt and statement/demo histories
          cannot be mixed until bank reconciliation is available. A receipt does
          not prove a payment or the sender’s authenticity.
        </p>
        <p>
          Choose one .eml file (1 MB maximum). Explicitly labelled English INR
          paid receipts are supported. Attachments and remote content are
          ignored. Missing or ambiguous values need your correction and
          approval.
        </p>
        {!previewId && (
          <div
            className="dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              void choose(event.dataTransfer.files[0]);
            }}
          >
            <label className="file-label">
              Choose synthetic receipt
              <input
                ref={picker}
                type="file"
                aria-label="Choose synthetic receipt"
                accept=".eml,message/rfc822"
                disabled={busy}
                onChange={(event) => {
                  void choose(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
            </label>
            <p>Drop a synthetic EML here, or use the file picker.</p>
          </div>
        )}
        {busy && <Loading text="Reading synthetic receipt…" />}
        {error && <ErrorState error={new Error(error)} />}
      </div>
      {previewId && file && (
        <StatementReview
          key={previewId}
          jobId={previewId}
          file={file}
          onImported={(id) => {
            setPreviewId(null);
            setFile(null);
            onImported(id);
          }}
          onCancel={() => {
            setPreviewId(null);
            setFile(null);
            requestAnimationFrame(() => picker.current?.focus());
          }}
          onRetry={() => {
            setPreviewId(null);
            setFile(null);
          }}
        />
      )}
    </section>
  );
}
