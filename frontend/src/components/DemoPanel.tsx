import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Dialog, ErrorState, Loading } from "./Common";
import { UploadProgress } from "./UploadProgress";

export function DemoPanel({ settings = false }: { settings?: boolean }) {
  const client = useQueryClient();
  const [removing, setRemoving] = useState(false);
  const [uploadId, setUploadId] = useState<string>();
  const [notice, setNotice] = useState("");
  const uploads = useQuery({
    queryKey: ["uploads", "demo"],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/uploads", {
          signal,
          params: { query: { limit: 100 } },
        })
      ).data!,
  });
  const demo = uploads.data?.items.find((item) => item.source === "demo");
  const progress = useQuery({
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
      const state = query.state.data;
      return state && ["done", "failed"].includes(state.status)
        ? false
        : Math.min(3000, 400 * (query.state.dataUpdateCount + 1));
    },
  });
  useEffect(() => {
    if (progress.data?.status === "done")
      void client.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "upload",
      });
  }, [progress.data?.status, client]);
  const load = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/demo/load")).data!,
    onSuccess: (item) => {
      setUploadId(item.id);
      setNotice("");
      void client.invalidateQueries({ queryKey: ["uploads"] });
    },
  });
  const remove = useMutation({
    mutationFn: async () => (await api.DELETE("/api/v1/demo/data")).data!,
    onSuccess: () => {
      setRemoving(false);
      setUploadId(undefined);
      setNotice("Demo data removed. Your account is ready for an upload.");
      void client.invalidateQueries();
    },
  });
  if (uploads.isPending) return <Loading text="Checking demo availability…" />;
  if (uploads.isError)
    return (
      <ErrorState
        error={uploads.error}
        retry={() => {
          void uploads.refetch();
        }}
      />
    );
  if (!demo && uploads.data?.total && !settings) return null;
  return (
    <section className="panel demo-panel" aria-label="Demo workspace">
      {demo ? (
        <>
          <p>
            <span className="badge">Demo data</span> Synthetic history generated
            as of <strong>{demo.demo_as_of}</strong>. Remove and reload to
            refresh the demo clock.
          </p>
          {settings && (
            <button onClick={() => setRemoving(true)}>Remove demo data</button>
          )}
        </>
      ) : (
        <>
          <h2>Explore with synthetic data</h2>
          <p>
            No bank connection, API key or SMTP server needed. Demo loading
            requires an empty account. Demo defaults include a budget and an
            example notification address.
          </p>
          <button
            className="primary"
            disabled={load.isPending || !!uploads.data?.total}
            onClick={() => load.mutate()}
          >
            {load.isPending ? "Preparing demo…" : "Load demo data"}
          </button>
          {!!uploads.data?.total && (
            <p>Use a separate empty account to explore the demo.</p>
          )}
        </>
      )}
      {load.isError && <ErrorState error={load.error} />}
      {progress.isError && (
        <ErrorState
          error={progress.error}
          retry={() => {
            void progress.refetch();
          }}
        />
      )}
      {uploadId && progress.data && <UploadProgress upload={progress.data} />}
      {progress.data?.status === "done" && uploadId && (
        <button onClick={() => setUploadId(undefined)}>
          Dismiss import result
        </button>
      )}
      {notice && <p role="status">{notice}</p>}
      {removing && (
        <Dialog title="Remove demo data?" onClose={() => setRemoving(false)}>
          <p>
            This removes synthetic uploads and their derived records, chat
            history and dev outbox copies when no real data remains. Your
            account and changed preferences stay.
          </p>
          <button disabled={remove.isPending} onClick={() => remove.mutate()}>
            {remove.isPending ? "Removing…" : "Confirm remove demo"}
          </button>
          {remove.isError && <ErrorState error={remove.error} />}
        </Dialog>
      )}
    </section>
  );
}
