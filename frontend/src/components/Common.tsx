import { useEffect, useRef, type ReactNode } from "react";
import { AlertCircle, Inbox, X } from "lucide-react";
import { errorMessage } from "../api/client";
import type { components } from "../api/schema";
import { dateLabel, formatMoney, label } from "../lib/money";

export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error" role="alert">
      <AlertCircle size={18} />
      <span>{errorMessage(error)}</span>
      {retry && <button onClick={retry}>Try again</button>}
    </div>
  );
}
export function Loading({ text = "Loading your data…" }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {text}
    </div>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Inbox size={30} />
      <p>{children}</p>
    </div>
  );
}
export function Heading({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {children}
    </header>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  drawer = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current!;
    dialog.showModal();
    return () => {
      dialog.close();
      if (previous?.isConnected) previous.focus();
      else document.querySelector<HTMLElement>("#content")?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "drawer" : ""}
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="dialog-header">
        <h2 id="dialog-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export const categories: components["schemas"]["SubscriptionOut"]["category"][] =
  [
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
  ];
export function CategoryOptions({
  knownOnly = false,
}: {
  knownOnly?: boolean;
}) {
  return categories
    .filter((value) => !knownOnly || value !== "unknown")
    .map((value) => (
      <option key={value} value={value}>
        {label(value)}
      </option>
    ));
}
export function Notices({
  item,
}: {
  item: components["schemas"]["SubscriptionOut"];
}) {
  return (
    <div className="notices">
      {item.requires_confirmation && (
        <span className="badge warning">Needs category confirmation</span>
      )}
      {!item.user_confirmed && (
        <span className="badge">Unconfirmed detection</span>
      )}
      {item.possibly_cancelled && (
        <span className="badge warning">
          May have stopped · {item.missed_cycles} missed cycles
        </span>
      )}
      {item.price_increase && (
        <span className="badge warning">
          Possible price increase:{" "}
          {formatMoney(item.price_increase.previous_amount)} →{" "}
          {formatMoney(item.price_increase.new_amount)}
        </span>
      )}
    </div>
  );
}
export function RenewalRows({
  items,
}: {
  items: components["schemas"]["SubscriptionOut"][];
}) {
  if (!items.length)
    return <Empty>No renewals expected in the next 30 days.</Empty>;
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Scrollable data table"
    >
      <table>
        <thead>
          <tr>
            <th>Merchant</th>
            <th>Cadence</th>
            <th>Next expected</th>
            <th>Amount per charge</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{label(item.merchant)}</strong>
                <Notices item={item} />
              </td>
              <td>{label(item.cadence)}</td>
              <td>
                {dateLabel(item.next_expected)}
                <small>Estimated from past charges</small>
              </td>
              <td className="money">
                {formatMoney(item.avg_amount, item.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
