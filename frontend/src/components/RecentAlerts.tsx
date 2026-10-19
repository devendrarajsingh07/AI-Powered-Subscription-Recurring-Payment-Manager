import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { dateLabel, label } from "../lib/money";
import { Empty, ErrorState, Loading } from "./Common";

export function RecentAlerts() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["alerts", offset],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/alerts", {
          signal,
          params: { query: { limit: 10, offset } },
        })
      ).data!,
    refetchInterval: 15_000,
  });
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Recent alerts</h2>
          <p className="muted">Scheduled events and actual delivery results</p>
        </div>
        <button
          disabled={query.isFetching}
          onClick={() => {
            void query.refetch();
          }}
        >
          Refresh alerts
        </button>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      ) : (
        <>
          {query.data.items.length === 0 ? (
            <Empty>
              No alerts recorded yet. Daily checks use your saved preferences.
            </Empty>
          ) : (
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Alert delivery history"
            >
              <table>
                <caption className="sr-only">Alert delivery history</caption>
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Send on</th>
                    <th>Status</th>
                    <th>Delivery details</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>{label(item.kind)}</td>
                      <td>{dateLabel(item.send_on)}</td>
                      <td>
                        <span
                          className={`badge ${item.status === "sent" ? "positive" : ["failed", "retrying", "skipped"].includes(item.status) ? "warning" : ""}`}
                        >
                          {label(item.status)}
                        </span>
                      </td>
                      <td>
                        {item.sent_at ? (
                          <time dateTime={item.sent_at}>
                            Sent{" "}
                            {new Intl.DateTimeFormat("en-IN", {
                              dateStyle: "medium",
                              timeStyle: "short",
                            }).format(new Date(item.sent_at))}
                          </time>
                        ) : (
                          item.safe_failure_reason ||
                          "Waiting for its scheduled check"
                        )}
                        <small>
                          {item.attempt_count} delivery attempts
                          {item.next_attempt_at && item.status === "retrying"
                            ? ` · Retry after ${new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.next_attempt_at))}`
                            : ""}
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <span>{query.data.total} alert events</span>
            <button disabled={!offset} onClick={() => setOffset(offset - 10)}>
              Previous alerts
            </button>
            <button
              disabled={offset + 10 >= query.data.total}
              onClick={() => setOffset(offset + 10)}
            >
              Next alerts
            </button>
          </div>
        </>
      )}
    </section>
  );
}
