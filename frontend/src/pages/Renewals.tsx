import { useState } from "react";
import { useRenewals } from "../hooks/data";
import {
  ErrorState,
  Heading,
  Loading,
  RenewalRows,
} from "../components/Common";
export default function Renewals() {
  const [offset, setOffset] = useState(0);
  const query = useRenewals(20, offset);
  return (
    <>
      <Heading
        title="Renewals, on your radar"
        subtitle="Expected charges over the next 30 days. Dates are estimates, not guarantees."
      />
      <div className="notice-box">
        Overdue estimates are rolled forward by the API. A missed cycle may mean
        a plan has stopped; it does not confirm cancellation.
      </div>
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
        ) : (
          <>
            <RenewalRows items={query.data.items} />
            <div className="pagination">
              <span>{query.data.total} expected renewals</span>
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
