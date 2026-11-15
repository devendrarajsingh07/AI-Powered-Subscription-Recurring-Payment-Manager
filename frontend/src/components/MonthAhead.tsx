import { useState } from "react";
import type { components } from "../api/schema";
import { formatMoney, label, paise } from "../lib/money";

type Item = components["schemas"]["SubscriptionOut"];
const DAY = 86_400_000;
const utc = (iso: string) => {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(year, month - 1, day);
};
const weekday = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  timeZone: "UTC",
});
const monthName = new Intl.DateTimeFormat("en-IN", {
  month: "short",
  timeZone: "UTC",
});
const longDate = new Intl.DateTimeFormat("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "UTC",
});
const amountOf = (item: Item) => item.billing_amount ?? item.avg_amount;
/** Exact paise back to an API-style decimal string; no floats touch money. */
const decimal = (value: bigint) =>
  `${value / 100n}.${String(value % 100n).padStart(2, "0")}`;

/** Thirty days of expected charges, one cell per day. */
export function MonthAhead({ items }: { items: Item[] }) {
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const dates = items.map((item) => utc(item.next_expected));
  // A demo or fixed clock can sit outside the browser's month; follow the data then.
  const start = dates.every((date) => date >= today && date < today + 30 * DAY)
    ? today
    : Math.min(...dates);
  const days = Array.from({ length: 30 }, (_, index) => {
    const time = start + index * DAY;
    const due = items.filter((_, position) => dates[position] === time);
    const total = due.reduce((sum, item) => sum + paise(amountOf(item)), 0n);
    return { time, due, total };
  });
  const highest = days.reduce(
    (max, day) => (day.total > max ? day.total : max),
    1n,
  );
  const first = days.find((day) => day.due.length)?.time;
  const [chosen, setChosen] = useState<number | undefined>();
  const selected =
    days.find((day) => day.time === chosen && day.due.length) ??
    days.find((day) => day.time === first);
  return (
    <section className="ahead" aria-labelledby="ahead-title">
      <div className="section-heading">
        <div>
          <h2 id="ahead-title">The next 30 days</h2>
          <p className="muted">
            Expected charges by day. Choose a marked day to see what is due.
          </p>
        </div>
      </div>
      <ol className="ahead-grid">
        {days.map((day, index) => {
          const date = new Date(day.time);
          const number = date.getUTCDate();
          const top =
            index === 0 || number === 1
              ? monthName.format(date)
              : weekday.format(date).slice(0, 2);
          const weekend = [0, 6].includes(date.getUTCDay()) ? " weekend" : "";
          if (!day.due.length)
            return (
              <li key={day.time} aria-hidden="true">
                <span className={"ahead-day" + weekend}>
                  {top}
                  <b>{number}</b>
                </span>
              </li>
            );
          const level =
            day.total * 3n > highest * 2n
              ? 3
              : day.total * 3n > highest
                ? 2
                : 1;
          return (
            <li key={day.time}>
              <button
                type="button"
                className={"ahead-day" + weekend}
                aria-pressed={selected?.time === day.time}
                onClick={() => setChosen(day.time)}
              >
                <span aria-hidden="true">{top}</span>
                <b aria-hidden="true">{number}</b>
                <i className={`level-${level}`} />
                <span className="sr-only">
                  {`${longDate.format(date)}: ${day.due.length} expected, ${formatMoney(decimal(day.total))}`}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      {selected && (
        <div className="ahead-readout" aria-live="polite">
          <strong>{longDate.format(new Date(selected.time))}</strong>
          <ul>
            {selected.due.map((item) => (
              <li key={item.id}>
                {`${label(item.merchant)} ${formatMoney(amountOf(item), item.currency)}`}
              </li>
            ))}
          </ul>
          <span className="money">
            {`${formatMoney(decimal(selected.total))} due that day`}
          </span>
        </div>
      )}
    </section>
  );
}
