import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getCompare = vi.fn();
vi.mock("@/lib/api", () => ({ getCompare: (...a: unknown[]) => getCompare(...a) }));
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
}));

import { CompareTab } from "./compare-tab";

afterEach(() => vi.restoreAllMocks());

const result = (over = {}) => ({
  preset: "weekdays_weekends",
  metric: "spend",
  buckets: [
    { label: "Weekdays", total: 2250, per_day: 75, n_days: 30 },
    { label: "Weekends", total: 2300, per_day: 287.5, n_days: 8 },
  ],
  labels: { a: "Weekdays", b: "Weekends" },
  categories: [
    { name: "Housing", a: 2000, b: 2000 },
    { name: "Groceries", a: 250, b: 300 },
  ],
  ...over,
});

test("renders bucket totals and grouped category bars", async () => {
  getCompare.mockResolvedValue(result());
  render(<CompareTab personId={1} filters={{}} />);

  await waitFor(() => expect(screen.getByText("Housing")).toBeInTheDocument());
  // both bucket labels present (legend + KPI)
  expect(screen.getAllByText("Weekdays").length).toBeGreaterThan(0);
  expect(screen.getByText("Groceries")).toBeInTheDocument();
});

test("preset and measure toggles refetch with new params", async () => {
  getCompare.mockResolvedValue(result());
  render(<CompareTab personId={1} filters={{}} />);
  await waitFor(() => expect(getCompare).toHaveBeenCalled());

  fireEvent.click(screen.getByText("This vs last month"));
  await waitFor(() =>
    expect(getCompare).toHaveBeenLastCalledWith(expect.objectContaining({ preset: "month_vs_month", metric: "spend" })),
  );

  fireEvent.click(screen.getByText("Per day"));
  await waitFor(() =>
    expect(getCompare).toHaveBeenLastCalledWith(expect.objectContaining({ preset: "month_vs_month", metric: "per_day" })),
  );
});
