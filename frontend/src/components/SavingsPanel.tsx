import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api/client";
import { formatMoney } from "../lib/money";
import { ErrorState, Loading } from "./Common";

export function SavingsPanel() {
  const query = useQuery({
    queryKey: ["savings"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/summary/savings", { signal })).data!,
  });
  return (
    <section className="panel savings-panel" aria-labelledby="savings-title">
      <div>
        <h2 id="savings-title">Potential monthly savings</h2>
        <p className="muted">
          Open overlap recommendations only. Estimates assume keeping one
          most-expensive plan in each group.
        </p>
        {query.isPending ? (
          <Loading text="Loading saving estimates…" />
        ) : query.isError ? (
          <ErrorState
            error={query.error}
            retry={() => {
              void query.refetch();
            }}
          />
        ) : (
          <>
            <strong className="savings-value" data-testid="potential-savings">
              {formatMoney(query.data.potential_savings, query.data.currency)}
            </strong>
            {query.data.potential_savings === "0.00" && (
              <small>No open duplicate estimates right now.</small>
            )}
          </>
        )}
      </div>
      <Link className="button" to="/recommendations">
        Review recommendations
      </Link>
    </section>
  );
}
