import { DemoPanel } from "../components/DemoPanel";
import { Link } from "react-router";
import {
  ArrowUpRight,
  CalendarDays,
  CreditCard,
  Layers,
  Upload,
  Wallet,
} from "lucide-react";
import { useRenewals, useSummary, useTrend } from "../hooks/data";
import {
  ErrorState,
  Heading,
  Loading,
  RenewalRows,
} from "../components/Common";
import { formatMoney } from "../lib/money";
import { SpendCharts } from "../components/SpendCharts";
import { SavingsPanel } from "../components/SavingsPanel";
import { MonthAhead } from "../components/MonthAhead";
import { ImportWalkthrough } from "../cinematic/ImportWalkthrough";
import { useAuthMode } from "../components/AuthMode";
export default function Dashboard() {
  const summary = useSummary();
  const trend = useTrend();
  const renewals = useRenewals(100);
  const mode = useAuthMode();
  return (
    <>
      <Heading
        title="Your recurring spend"
        subtitle="A clearer picture of every renewal."
      >
        {mode.data?.public_demo_only === false && (
          <Link className="button primary" to="/upload">
            <Upload size={17} />
            Upload statement
          </Link>
        )}
      </Heading>
      <DemoPanel />
      {summary.isPending ? (
        <Loading />
      ) : summary.isError ? (
        <ErrorState
          error={summary.error}
          retry={() => {
            void summary.refetch();
          }}
        />
      ) : (
        <>
          <div className="kpi-grid">
            <article>
              <div className="kpi-label">
                <span>Monthly equivalent</span>
                <Wallet size={18} />
              </div>
              <strong data-testid="monthly-total">
                {formatMoney(summary.data.monthly_equivalent)}
              </strong>
              <small>Subscriptions + fixed bills</small>
            </article>
            <article>
              <div className="kpi-label">
                <span>Yearly total</span>
                <CalendarDays size={18} />
              </div>
              <strong data-testid="yearly-total">
                {formatMoney(summary.data.yearly_total)}
              </strong>
              <small>Equivalent recurring spend</small>
            </article>
            <article>
              <div className="kpi-label">
                <span>Active subscriptions</span>
                <CreditCard size={18} />
              </div>
              <strong>{summary.data.subscriptions.count}</strong>
              <small>
                {formatMoney(summary.data.subscriptions.monthly_equivalent)} /
                month
              </small>
            </article>
            <article>
              <div className="kpi-label">
                <span>Fixed bills</span>
                <Layers size={18} />
              </div>
              <strong>
                {formatMoney(summary.data.fixed_bills.monthly_equivalent)}
              </strong>
              <small>
                {summary.data.fixed_bills.count} bills · monthly equivalent
              </small>
            </article>
          </div>
          {!summary.data.active_count && (
            <div className="notice-box">
              {mode.data?.public_demo_only === false ? (
                <>
                  {" "}
                  <Link to="/upload">Upload a statement</Link> or load the
                  synthetic demo to explore recurring payments.
                </>
              ) : (
                "Load the sample data to explore recurring payments."
              )}
            </div>
          )}
        </>
      )}
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Upcoming renewals</h2>
            <p className="muted">Next expected charges in the next 30 days</p>
          </div>
          <Link to="/renewals">
            View all <ArrowUpRight size={15} />
          </Link>
        </div>
        {renewals.isPending ? (
          <Loading />
        ) : renewals.isError ? (
          <ErrorState
            error={renewals.error}
            retry={() => {
              void renewals.refetch();
            }}
          />
        ) : (
          <RenewalRows items={renewals.data.items.slice(0, 5)} />
        )}
      </section>
      <SavingsPanel />
      <ImportWalkthrough />
      {!!renewals.data?.items.length && (
        <MonthAhead items={renewals.data.items} />
      )}
      {summary.data && (
        <SpendCharts
          summary={summary.data}
          trend={trend.data}
          pending={trend.isPending}
          error={trend.error}
          retry={() => {
            void trend.refetch();
          }}
        />
      )}
    </>
  );
}
