import { describe, expect, test } from "vitest";
import { chartCoordinates, compareDecimals, formatMoney, paise } from "./money";
describe("decimal-safe money", () => {
  test.each([
    ["0", "₹0.00"],
    ["1.1", "₹1.10"],
    ["1234567.89", "₹12,34,567.89"],
    ["999999999999999999.99", "₹9,99,99,99,99,99,99,99,999.99"],
    ["000123.01", "₹123.01"],
  ])("formats %s", (value, expected) =>
    expect(formatMoney(value)).toBe(expected),
  );
  test("rejects invalid values without showing invented figures", () => {
    expect(formatMoney("NaN")).toBe("Unavailable");
    expect(() => paise("1.001")).toThrow();
  });
  test("compares decimals beyond safe integer and sorts without float drift", () => {
    expect(
      compareDecimals("999999999999999999.98", "999999999999999999.99"),
    ).toBe(-1);
    expect(compareDecimals("10.1", "10.10")).toBe(0);
    expect(["10", "2.01", "2.00"].sort(compareDecimals)).toEqual([
      "2.00",
      "2.01",
      "10",
    ]);
  });
  test("chart coordinates are dimensionless; original monetary strings stay exact", () => {
    const values = ["0.01", "0.02"];
    expect(chartCoordinates(values)).toEqual([5000, 10000]);
    expect(values).toEqual(["0.01", "0.02"]);
  });
});
