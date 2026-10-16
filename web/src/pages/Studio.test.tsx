import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const getOverview = vi.fn();
const getNetWorth = vi.fn();
const getCategoryTrend = vi.fn();
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {} }),
  getActiveCurrency: () => "USD",
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({
  getOverview: (...a: unknown[]) => getOverview(...a),
  getNetWorth: (...a: unknown[]) => getNetWorth(...a),
  getCategoryTrend: (...a: unknown[]) => getCategoryTrend(...a),
}));

import Studio from "./Studio";

beforeEach(() => {
  localStorage.clear();
  getOverview.mockResolvedValue({
    month: "2026-06", months: [], income: 0, spend: 0, net: 0, savings_rate: 0.2, complete: false,
    by_category: { Housing: 2000 }, alerts: [], series: [
      { month: "2026-05", income: 5000, spend: 3000, net: 2000, savings_rate: 0.4, complete: true },
      { month: "2026-06", income: 5000, spend: 4500, net: 500, savings_rate: 0.1, complete: false },
    ], split: null, uncategorized: { count: 0, amount: 0 }, safe_to_spend: 0, committed: 0,
    committed_spent: 0, discretionary_spent: 0, bills_due: { count: 0, amount: 0 },
  });
  getNetWorth.mockResolvedValue({ summary: { assets: 0, liabilities: 0, net: 0 }, delta: null, accounts: [], trend: [], split: null });
  getCategoryTrend.mockResolvedValue({ months: [], series: [] });
});
afterEach(() => vi.clearAllMocks());

test("shows the plain-English spec sentence and updates it as controls change", async () => {
  render(<Studio />);
  expect(screen.getByText(/Net saved, last 12 months — as an area chart\./)).toBeInTheDocument();
  // Switch the chart type to Line (the kind pills are buttons labelled by text).
  await userEvent.click(screen.getByText("Line"));
  expect(screen.getByText(/as a line chart\./)).toBeInTheDocument();
});

test("disables chart types that don't suit the measure", async () => {
  render(<Studio />);
  // Default measure "Net saved" supports area/line/bar but not donut.
  expect(screen.getByRole("button", { name: "Donut" })).toBeDisabled();
});

const boardOf = () => screen.getByRole("heading", { name: "My Charts" }).parentElement!;

test("pinning a chart adds it to the My Charts board and persists", async () => {
  const { unmount } = render(<Studio />);
  expect(within(boardOf()).getByText(/No saved charts yet/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Pin to My Charts/i }));
  // A saved card with the default (sentence-derived) title appears on the board.
  await waitFor(() => expect(within(boardOf()).getByText(/Net saved, last 12 months/)).toBeInTheDocument());

  // Re-mount: the pinned chart was persisted to localStorage.
  unmount();
  render(<Studio />);
  expect(within(boardOf()).getByText(/Net saved, last 12 months/)).toBeInTheDocument();
});
