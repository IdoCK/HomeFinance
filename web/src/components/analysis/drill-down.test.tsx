import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getDrill = vi.fn();
vi.mock("@/lib/api", () => ({ getDrill: (...a: unknown[]) => getDrill(...a) }));
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
}));

import { DrillDown } from "./drill-down";

afterEach(() => vi.restoreAllMocks());

test("drills category → vendor → rows and climbs back via breadcrumb", async () => {
  const categories = { level: "category", items: [{ name: "Groceries", value: 550 }], rows: [] };
  getDrill
    .mockResolvedValue(categories) // fallback for the breadcrumb climb back to categories
    .mockResolvedValueOnce(categories)
    .mockResolvedValueOnce({ level: "vendor", items: [{ name: "Whole Foods", value: 550 }], rows: [] })
    .mockResolvedValueOnce({ level: "rows", items: [], rows: [
      { date: "2026-05-18", description: "Whole Foods", amount: -250, category: "Groceries" },
    ] });

  render(<DrillDown personId={1} filters={{}} />);

  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("Drill into Groceries"));

  await waitFor(() => expect(screen.getByLabelText("Drill into Whole Foods")).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("Drill into Whole Foods"));

  // rows leaf
  await waitFor(() => expect(screen.getByText("-$250.00")).toBeInTheDocument());
  expect(getDrill).toHaveBeenLastCalledWith(expect.objectContaining({ level: "rows", cat: "Groceries", vendor: "Whole Foods" }));

  // breadcrumb back to categories
  fireEvent.click(screen.getByRole("button", { name: "All categories" }));
  await waitFor(() => expect(screen.getByLabelText("Drill into Groceries")).toBeInTheDocument());
});
