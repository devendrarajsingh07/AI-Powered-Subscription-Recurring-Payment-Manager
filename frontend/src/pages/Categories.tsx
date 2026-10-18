import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import {
  CategoryOptions,
  Empty,
  ErrorState,
  Heading,
  Loading,
} from "../components/Common";
import { useRefresh } from "../hooks/data";
import { label } from "../lib/money";
export default function Categories() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["categories", offset],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/categories/unconfirmed", {
          signal,
          params: { query: { limit: 20, offset } },
        })
      ).data!,
  });
  return (
    <>
      <Heading
        title="A little context helps"
        subtitle="Confirm categories for merchants the rules could not resolve."
      />
      <p className="notice-box">
        Your choice applies to this merchant’s detected products. Rent, loans,
        insurance and utilities are tracked as fixed bills.
      </p>
      <section className="panel">
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            error={query.error}
            retry={() => {
              void query.refetch();
            }}
          />
        ) : !query.data.items.length ? (
          <>
            <Empty>
              {query.data.total
                ? "No merchants on this page."
                : "No merchants need category confirmation."}
            </Empty>
            {offset > 0 && (
              <button onClick={() => setOffset(Math.max(0, offset - 20))}>
                Previous
              </button>
            )}
          </>
        ) : (
          <>
            {query.data.items.map((item) => (
              <CategoryRow key={item.id} item={item} />
            ))}
            <div className="pagination">
              <span>{query.data.total} merchants to review</span>
              <button disabled={!offset} onClick={() => setOffset(offset - 20)}>
                Previous
              </button>
              <button
                disabled={offset + 20 >= query.data.total}
                onClick={() => setOffset(offset + 20)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
function CategoryRow({ item }: { item: components["schemas"]["CategoryOut"] }) {
  const [category, setCategory] = useState<
    components["schemas"]["CategoryPatch"]["category"] | ""
  >(item.category === "unknown" ? "" : item.category);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useRefresh();
  return (
    <form
      className="category-row"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!category) return;
        setBusy(true);
        setError("");
        try {
          await api.PATCH("/api/v1/categories/{category_id}", {
            params: { path: { category_id: item.id } },
            body: { category },
          });
          await refresh();
        } catch (caught) {
          setError(errorMessage(caught));
        } finally {
          setBusy(false);
        }
      }}
    >
      <div>
        <strong>{label(item.merchant)}</strong>
        <small>
          Current: {label(item.category)} · {item.source}
        </small>
      </div>
      <label>
        Category for {item.merchant}
        <select
          required
          value={category}
          onChange={(event) =>
            setCategory(event.target.value as typeof category)
          }
        >
          <option value="">Choose a category</option>
          <CategoryOptions knownOnly />
        </select>
      </label>
      <button className="primary" disabled={busy || !category}>
        {busy ? "Saving…" : "Confirm category"}
      </button>
      {error && <ErrorState error={new Error(error)} />}
    </form>
  );
}
