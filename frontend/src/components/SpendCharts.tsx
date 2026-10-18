import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import type { components } from "../api/schema";
import { chartCoordinates, formatMoney, label } from "../lib/money";
import { Empty, ErrorState, Loading } from "./Common";
type Summary = components["schemas"]["Summary"];
type Trend = components["schemas"]["Trend"];
const palette = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];
export function SpendCharts({
  summary,
  trend,
  pending,
  error,
  retry,
}: {
  summary: Summary;
  trend?: Trend;
  pending: boolean;
  error: unknown;
  retry: () => void;
}) {
  const [tables, setTables] = useState(false);
  const trendCoordinates = chartCoordinates(
    trend?.months.map((point) => point.total) || [],
  );
  const points =
    trend?.months.map((point, index) => ({
      ...point,
      coordinate: trendCoordinates[index],
    })) || [];
  const categoryCoordinates = chartCoordinates(
    summary.categories.map((item) => item.monthly_equivalent),
  );
  const slices = summary.categories.map((item, index) => ({
    ...item,
    name:
      label(item.category) +
      (item.kind === "fixed_bill" ? " · fixed bill" : ""),
    coordinate: categoryCoordinates[index],
  }));
  return (
    <>
      <div className="chart-controls">
        <span className="eyebrow">THE BIG PICTURE</span>
        <button aria-pressed={tables} onClick={() => setTables(!tables)}>
          {tables ? "Show charts" : "Show data tables"}
        </button>
      </div>
      <div className="chart-grid">
        <section className="panel">
          <h2>Spending over time</h2>
          <p className="muted">Actual detected charges · last 12 months</p>
          {pending ? (
            <Loading />
          ) : error ? (
            <ErrorState error={error} retry={retry} />
          ) : !points.some((point) => point.total !== "0.00") ? (
            <Empty>No detected charges in this period.</Empty>
          ) : tables ? (
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable data table"
            >
              <table>
                <caption>Actual charges by month</caption>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Subscriptions</th>
                    <th>Fixed bills</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((point) => (
                    <tr key={point.month}>
                      <th>{point.month}</th>
                      <td>{formatMoney(point.subscriptions)}</td>
                      <td>{formatMoney(point.fixed_bills)}</td>
                      <td>{formatMoney(point.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              className="chart"
              role="img"
              aria-label="Trend of actual recurring charges. Use Show data tables for exact amounts."
            >
              <ResponsiveContainer width="100%" height={245}>
                <AreaChart
                  data={points}
                  margin={{ top: 20, right: 15, left: 15, bottom: 0 }}
                >
                  <CartesianGrid
                    vertical={false}
                    stroke="var(--border)"
                    strokeDasharray="3 4"
                  />
                  <XAxis
                    dataKey="month"
                    tickFormatter={(value) => String(value).slice(5)}
                    stroke="var(--muted)"
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={({ active, payload }) =>
                      active && payload?.[0] ? (
                        <div className="chart-tooltip">
                          {payload[0].payload.month}
                          <strong>
                            {formatMoney(payload[0].payload.total)}
                          </strong>
                        </div>
                      ) : null
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="coordinate"
                    stroke="var(--accent)"
                    fill="var(--accent-soft)"
                    strokeWidth={2.5}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
        <section className="panel">
          <h2>By category</h2>
          <p className="muted">Monthly equivalent · all recurring payments</p>
          {!slices.length ? (
            <Empty>Upload a statement to see categories.</Empty>
          ) : tables ? (
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable data table"
            >
              <table>
                <caption>Category monthly equivalents</caption>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {slices.map((item, index) => (
                    <tr key={index}>
                      <th>{item.name}</th>
                      <td>{formatMoney(item.monthly_equivalent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <>
              <div
                className="donut"
                role="img"
                aria-label="Recurring spend by category. A labelled legend and data table alternative are available."
              >
                <ResponsiveContainer width="100%" height={190}>
                  <PieChart>
                    <Pie
                      data={slices}
                      dataKey="coordinate"
                      nameKey="name"
                      innerRadius={54}
                      outerRadius={78}
                      paddingAngle={3}
                      stroke="none"
                      isAnimationActive={false}
                    >
                      {slices.map((_, index) => (
                        <Cell
                          key={index}
                          fill={palette[index % palette.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      content={({ active, payload }) =>
                        active && payload?.[0] ? (
                          <div className="chart-tooltip">
                            {payload[0].payload.name}
                            <strong>
                              {formatMoney(
                                payload[0].payload.monthly_equivalent,
                              )}
                            </strong>
                          </div>
                        ) : null
                      }
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="chart-legend">
                {slices.map((item, index) => (
                  <li key={index}>
                    <span>
                      <i
                        style={{ background: palette[index % palette.length] }}
                      />
                      {item.name}
                    </span>
                    <strong>{formatMoney(item.monthly_equivalent)}</strong>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </>
  );
}
