import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getDrill = vi.fn();
const getVendors = vi.fn().mockResolvedValue([]);
const ungroupVendor = vi.fn().mockResolvedValue({ ok: true, name: "", keywords: [] });
vi.mock("@/lib/api", () => ({
  getDrill: (...a: unknown[]) => getDrill(...a),
  getVendors: (...a: unknown[]) => getVendors(...a),
  groupVendor: () => Promise.resolve({ ok: true, name: "", keywords: [] }),
  ungroupVendor: (...a: unknown[]) => ungroupVendor(...a),
}));
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
  getActiveCurrency: () => "USD",
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

test("expands a vendor group and removes a member", async () => {
  const categories = { level: "category", items: [{ name: "Eating out", value: 200 }], rows: [] };
  getDrill.mockResolvedValue({ level: "vendor", items: [{ name: "lelabar", value: 200 }], rows: [] });
  getDrill.mockResolvedValueOnce(categories); // first call (top level) = categories
  getVendors.mockResolvedValue([
    { id: 7, person_id: 1, name: "lelabar", keywords: "lelabar,tst* sforno trattoria" },
  ]);

  render(<DrillDown personId={1} filters={{}} />);
  await waitFor(() => expect(screen.getByLabelText("Drill into Eating out")).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("Drill into Eating out"));

  // The group shows an expander (member count); opening it reveals member chips.
  await waitFor(() => expect(screen.getByLabelText(/Show merchants grouped under lelabar/i)).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText(/Show merchants grouped under lelabar/i));
  expect(screen.getByText("tst* sforno trattoria")).toBeInTheDocument();

  // ✕ on a member pulls it back out of the group.
  fireEvent.click(screen.getByLabelText("Remove tst* sforno trattoria from lelabar"));
  await waitFor(() =>
    expect(ungroupVendor).toHaveBeenCalledWith({ personId: 1, target: "lelabar", keyword: "tst* sforno trattoria" }),
  );
});
