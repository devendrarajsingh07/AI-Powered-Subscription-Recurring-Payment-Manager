import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import {
  CategoryOptions,
  Dialog,
  Empty,
  ErrorState,
  Heading,
  Loading,
  Notices,
} from "../components/Common";
import {
  useRefresh,
  useSubscriptions,
  type SubscriptionFilters,
} from "../hooks/data";
import { dateLabel, formatMoney, label } from "../lib/money";
type Subscription = components["schemas"]["SubscriptionOut"];
export function filtersFromSearch(
  params: URLSearchParams,
): SubscriptionFilters {
  const select = <const T extends string>(
    key: string,
    allowed: readonly T[],
  ): T | undefined => {
    const value = params.get(key);
    return allowed.includes(value as T) ? (value as T) : undefined;
  };
  const offset = params.get("offset") || "0";
  return {
    status: select("status", ["active", "cancelled", "dismissed"]),
    category: select("category", [
      "streaming",
      "music",
      "cloud",
      "fitness",
      "telecom",
      "software",
      "news",
      "rent",
      "loan",
      "insurance",
      "utilities",
      "unknown",
    ]),
    cadence: select("cadence", ["weekly", "monthly", "quarterly", "yearly"]),
    kind: select("kind", ["subscription", "fixed_bill"]),
    sort:
      select("sort", [
        "merchant",
        "avg_amount",
        "next_expected",
        "confidence",
      ]) || "merchant",
    direction: select("direction", ["asc", "desc"]) || "asc",
    limit: 20,
    offset:
      /^\d+$/.test(offset) && Number.isSafeInteger(Number(offset))
        ? Number(offset)
        : 0,
  };
}
export default function Subscriptions() {
  const [params, setParams] = useSearchParams();
  const filters = filtersFromSearch(params);
  const query = useSubscriptions(filters);
  const [selected, setSelected] = useState<string | null>(() =>
    params.get("review"),
  );
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "offset") next.delete("offset");
    setParams(next);
  }
  return (
    <>
      <Heading
        title="Every recurring payment"
        subtitle="Review detections, confirm the details and keep your subscriptions in view."
      />
      <section className="panel">
        <div className="filters">
          <label>
            Status
            <select
              value={filters.status || ""}
              onChange={(event) => filter("status", event.target.value)}
            >
              <option value="">All statuses</option>
              {["active", "dismissed", "cancelled"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Category
            <select
              value={filters.category || ""}
              onChange={(event) => filter("category", event.target.value)}
            >
              <option value="">All categories</option>
              <CategoryOptions />
            </select>
          </label>
          <label>
            Cadence
            <select
              value={filters.cadence || ""}
              onChange={(event) => filter("cadence", event.target.value)}
            >
              <option value="">All cadences</option>
              {["weekly", "monthly", "quarterly", "yearly"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Kind
            <select
              value={filters.kind || ""}
              onChange={(event) => filter("kind", event.target.value)}
            >
              <option value="">All payments</option>
              <option value="subscription">Subscriptions</option>
              <option value="fixed_bill">Fixed bills</option>
            </select>
          </label>
          <label>
            Sort by
            <select
              value={filters.sort || "merchant"}
              onChange={(event) => filter("sort", event.target.value)}
            >
              <option value="merchant">Merchant</option>
              <option value="avg_amount">Amount</option>
              <option value="next_expected">Next renewal</option>
              <option value="confidence">Confidence</option>
            </select>
          </label>
          <label>
            Direction
            <select
              value={filters.direction || "asc"}
              onChange={(event) => filter("direction", event.target.value)}
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </label>
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
            {!query.data.items.length ? (
              <Empty>
                No payments match these filters. Upload a statement or adjust
                your filters.
              </Empty>
            ) : (
              <div
                className="table-scroll"
                tabIndex={0}
                role="region"
                aria-label="Scrollable data table"
              >
                <table>
                  <caption className="sr-only">
                    Detected recurring payments
                  </caption>
                  <thead>
                    <tr>
                      <th>Merchant / category</th>
                      <th>Cadence</th>
                      <th>Average charge</th>
                      <th>Confidence</th>
                      <th>Next expected</th>
                      <th>Status</th>
                      <th>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <strong>{label(item.merchant)}</strong>
                          <small>
                            {label(item.category)} · {label(item.kind)}
                          </small>
                          <Notices item={item} />
                        </td>
                        <td>{label(item.cadence)}</td>
                        <td className="money">
                          {formatMoney(item.avg_amount, item.currency)}
                        </td>
                        <td>
                          <span
                            className={
                              Number(item.confidence) < 0.8
                                ? "badge warning"
                                : "badge"
                            }
                            title="Deterministic score from regularity, amount stability and occurrence count; not certainty."
                          >
                            {Number(item.confidence) < 0.8
                              ? "Lower confidence · "
                              : "Score "}
                            {String(item.confidence)}
                          </span>
                          <small>
                            {item.occurrences} charges ·{" "}
                            {item.user_confirmed
                              ? "Confirmed"
                              : "Review suggested"}
                          </small>
                        </td>
                        <td>{dateLabel(item.next_expected)}</td>
                        <td>
                          <span
                            className={`badge ${item.status === "active" ? "positive" : ""}`}
                          >
                            {label(item.status)}
                          </span>
                        </td>
                        <td>
                          <button
                            aria-label={`Review ${item.merchant}`}
                            onClick={(event) => {
                              // Safari does not focus buttons on pointer activation.
                              event.currentTarget.focus();
                              setSelected(item.id);
                            }}
                          >
                            Review
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="pagination">
              <span>
                {query.data.total} detected products · {query.data.offset}{" "}
                offset
              </span>
              <button
                disabled={!filters.offset}
                onClick={() =>
                  filter("offset", String((filters.offset || 0) - 20))
                }
              >
                Previous
              </button>
              <button
                disabled={(filters.offset || 0) + 20 >= query.data.total}
                onClick={() =>
                  filter("offset", String((filters.offset || 0) + 20))
                }
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
      {selected && (
        <ChargeDrawer
          id={selected}
          onClose={() => {
            setSelected(null);
            const next = new URLSearchParams(params);
            next.delete("review");
            setParams(next, { replace: true });
          }}
        />
      )}
    </>
  );
}
export function ChargeDrawer({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["subscription", id, offset],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/subscriptions/{subscription_id}", {
          signal,
          params: {
            path: { subscription_id: id },
            query: { charges_limit: 20, charges_offset: offset },
          },
        })
      ).data!,
  });
  return (
    <Dialog
      title={query.data ? label(query.data.merchant) : "Payment details"}
      onClose={onClose}
      drawer
    >
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
          <Notices item={query.data} />
          <p className="muted">
            Confidence score {String(query.data.confidence)} combines
            regularity, amount stability and occurrence count. It is an
            estimate; please review the underlying charges.
          </p>
          <DecisionForm
            item={query.data}
            updated={() => {
              void query.refetch();
            }}
          />
          <h3>Underlying charges</h3>
          {!query.data.charges.length ? (
            <Empty>No linked charges.</Empty>
          ) : (
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable data table"
            >
              <table>
                <thead>
                  <tr>
                    <th>Date / description</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.charges.map((charge) => (
                    <tr key={charge.id}>
                      <td>
                        {dateLabel(charge.date)}
                        <small className="charge-description">
                          {charge.description}
                        </small>
                      </td>
                      <td className="money">
                        {formatMoney(charge.amount, charge.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <span>{query.data.charges_total} linked charges</span>
            <button disabled={!offset} onClick={() => setOffset(offset - 20)}>
              Previous charges
            </button>
            <button
              disabled={offset + 20 >= query.data.charges_total}
              onClick={() => setOffset(offset + 20)}
            >
              Next charges
            </button>
          </div>
        </>
      )}
    </Dialog>
  );
}
function DecisionForm({
  item,
  updated,
}: {
  item: Subscription;
  updated: () => void;
}) {
  const [category, setCategory] = useState(item.category);
  const [lastUsed, setLastUsed] = useState(item.last_used_at || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const refresh = useRefresh();
  async function patch(body: components["schemas"]["SubscriptionPatch"]) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.PATCH("/api/v1/subscriptions/{subscription_id}", {
        params: { path: { subscription_id: item.id } },
        body,
      });
      await refresh();
      updated();
      setMessage("Changes saved.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="decision-form">
      <h3>Review this detection</h3>
      <div className="action-row">
        <button
          disabled={busy || item.user_confirmed}
          onClick={() => {
            void patch({ user_confirmed: true });
          }}
        >
          Confirm detection
        </button>
        <button
          disabled={busy || item.status === "dismissed"}
          onClick={() => {
            void patch({ status: "dismissed" });
          }}
        >
          Dismiss
        </button>
        <button
          disabled={busy || item.status === "cancelled"}
          onClick={() => {
            void patch({ status: "cancelled" });
          }}
        >
          Mark cancelled
        </button>
        {item.status !== "active" && (
          <button
            disabled={busy}
            onClick={() => {
              void patch({ status: "active" });
            }}
          >
            Mark active
          </button>
        )}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void patch({ category });
        }}
      >
        <label>
          Change category
          <select
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as Subscription["category"])
            }
          >
            <CategoryOptions />
          </select>
        </label>
        <button disabled={busy}>Save category</button>
      </form>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void patch({ last_used_at: lastUsed || null });
        }}
      >
        <label>
          Last used (optional)
          <input
            type="date"
            value={lastUsed}
            onChange={(event) => setLastUsed(event.target.value)}
          />
        </label>
        <small>
          Only you can tell us when you used a service. A blank date clears this
          signal.
        </small>
        <button disabled={busy}>Save last used</button>
      </form>
      {busy && <Loading text="Saving changes…" />}
      {error && <ErrorState error={new Error(error)} />}
      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}
    </div>
  );
}
