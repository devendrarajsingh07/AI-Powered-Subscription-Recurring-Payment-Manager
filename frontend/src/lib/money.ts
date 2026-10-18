/** Display API decimals without converting financial values to binary floats. */
export function formatMoney(value: string, currency = "INR"): string {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return "Unavailable";
  const [whole, fraction = ""] = value.split(".");
  const digits = whole.replace(/^0+(?=\d)/, "");
  const last = digits.slice(-3);
  const first = digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${currency === "INR" ? "₹" : currency + " "}${first ? first + "," : ""}${last}.${fraction.padEnd(2, "0")}`;
}
export function paise(value: string): bigint {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) throw new Error("Invalid decimal");
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}
export function compareDecimals(a: string, b: string): number {
  return paise(a) < paise(b) ? -1 : paise(a) > paise(b) ? 1 : 0;
}
/** Dimensionless chart coordinates only; never used for displayed financial figures. */
export function chartCoordinates(values: string[]): number[] {
  const integers = values.map(paise);
  const maximum = integers.reduce((a, b) => (a > b ? a : b), 1n);
  return integers.map((value) => Number((value * 10000n) / maximum));
}
export const dateLabel = (value: string) =>
  new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value.slice(0, 10) + "T12:00:00"));
export const label = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
