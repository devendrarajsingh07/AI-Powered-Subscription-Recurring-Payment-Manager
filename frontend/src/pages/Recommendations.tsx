import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { Empty, ErrorState, Heading, Loading } from "../components/Common";
import { useRefresh } from "../hooks/data";
import { formatMoney, label } from "../lib/money";

type Recommendation = components["schemas"]["RecommendationOut"];
const types: Recommendation["type"][] = [
  "duplicate",
  "high_cost",
  "price_increase",
  "possibly_unused",
];
const statuses: Recommendation["status"][] = [
  "open",
  "accepted",
  "dismissed",
  "resolved",
];

export default function Recommendations() {
  const [status, setStatus] = useState<Recommendation["status"] | "">("open");
  const [type, setType] = useState<Recommendation["type"] | "">("");
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const refresh = useRefresh();
  const query = useQuery({
    queryKey: ["recommendations", status, type, offset],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/recommendations", {
          signal,
          params: {
            query: {
              status: status || undefined,
              type: type || undefined,
              limit: 20,
              offset,
            },
          },
        })
      ).data!,
  });
  const mutation = useMutation({
    mutationFn: async ({
      id,
      action,
    }: {
      id: string;
      action: components["schemas"]["RecommendationPatch"]["action"];
    }) =>
      (
        await api.PATCH("/api/v1/recommendations/{recommendation_id}", {
          params: { path: { recommendation_id: id } },
          body: { action },
        })
      ).data!,
    onSuccess: async (result) => {
      setMessage(
        result.status === "accepted"
          ? "Review or cancellation intent recorded. Subscription statuses are unchanged."
          : "Recommendation dismissed. It may reappear if the underlying plan details change.",
      );
      await refresh();
    },
  });
  return (
    <>
      <Heading
        title="A few things worth reviewing"
        subtitle="Advisory insights from your recurring payments. No service is changed automatically."
      />
      <div className="notice-box">
        An estimate is an option to review, not financial advice. High-cost and
        usage notices have no saving estimate. Price increases show extra cost
        separately.
      </div>
      <section className="panel">
        <div className="filters">
          <label>
            Recommendation status
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as typeof status);
                setOffset(0);
              }}
            >
              <option value="">All statuses</option>
              {statuses.map((value) => (
                <option value={value} key={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Recommendation type
            <select
              value={type}
              onChange={(event) => {
                setType(event.target.value as typeof type);
                setOffset(0);
              }}
            >
              <option value="">All types</option>
              {types.map((value) => (
                <option value={value} key={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {message && (
          <p className="success" role="status">
            {message}
          </p>
        )}
        {mutation.isError && <ErrorState error={mutation.error} />}
        {mutation.isPending && <Loading text="Saving your decision…" />}
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
                No recommendations match these filters. We will keep checking
                when your data or decisions change.
              </Empty>
            ) : (
              <div className="recommendation-list">
                {query.data.items.map((item) => (
                  <RecommendationCard
                    item={item}
                    key={item.id}
                    busy={mutation.isPending}
                    decide={(action) =>
                      mutation.mutate({ id: item.id, action })
                    }
                  />
                ))}
              </div>
            )}
            <div className="pagination">
              <span>{query.data.total} recommendations</span>
              <button disabled={!offset} onClick={() => setOffset(offset - 20)}>
                Previous recommendations
              </button>
              <button
                disabled={offset + 20 >= query.data.total}
                onClick={() => setOffset(offset + 20)}
              >
                Next recommendations
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function RecommendationCard({
  item,
  busy,
  decide,
}: {
  item: Recommendation;
  busy: boolean;
  decide: (
    action: components["schemas"]["RecommendationPatch"]["action"],
  ) => void;
}) {
  return (
    <article className="recommendation-card" aria-labelledby={`rec-${item.id}`}>
      <div className="section-heading">
        <div>
          <span className="badge">{label(item.type)}</span>
          <h2 id={`rec-${item.id}`}>
            {item.type === "duplicate"
              ? `${label(item.members[0]?.category || "subscription")} overlap`
              : label(item.type)}
          </h2>
        </div>
        <span className={`badge ${item.status === "open" ? "warning" : ""}`}>
          {label(item.status)}
        </span>
      </div>
      <p>{item.message}</p>
      <div className="recommendation-estimate">
        {item.est_monthly_saving !== null ? (
          <>
            <span>Estimated monthly saving</span>
            <strong>{formatMoney(item.est_monthly_saving)}</strong>
          </>
        ) : (
          <span>No estimate</span>
        )}
        {item.extra_monthly_cost !== null && (
          <div>
            <span>Extra monthly-equivalent cost</span>
            <strong>{formatMoney(item.extra_monthly_cost)}</strong>
            {item.percent_change !== null && (
              <small>
                {item.percent_change}% price increase · extra cost, not a saving
              </small>
            )}
          </div>
        )}
      </div>
      <ul className="recommendation-members">
        {item.members.map((member) => (
          <li key={member.subscription_id}>
            <Link
              to={`/subscriptions?review=${encodeURIComponent(member.subscription_id)}`}
              aria-label={`Review ${member.merchant} ${label(member.category)}`}
            >
              {label(member.merchant)}
            </Link>
            <span>
              {label(member.cadence)} · {formatMoney(member.monthly_equivalent)}{" "}
              / month
            </span>
          </li>
        ))}
      </ul>
      {item.status === "accepted" && (
        <p className="notice-box">
          Intent recorded. To track an actual cancellation, mark the payment
          cancelled in Subscriptions.
        </p>
      )}
      {item.status !== "resolved" && (
        <div className="action-row">
          <button
            className="primary"
            disabled={busy || item.status !== "open"}
            onClick={() => decide("accept")}
          >
            Record review intent
          </button>
          <button
            disabled={busy || item.status === "dismissed"}
            onClick={() => decide("dismiss")}
          >
            Dismiss recommendation
          </button>
        </div>
      )}
    </article>
  );
}
