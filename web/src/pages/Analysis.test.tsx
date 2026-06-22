import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getFilterOptions = vi.fn();
const getCategoryTrend = vi.fn();
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", people: [], names: { you: "Ada", spouse: "Bo" }, setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({
  getFilterOptions: (...a: unknown[]) => getFilterOptions(...a),
  getCategoryTrend: (...a: unknown[]) => getCategoryTrend(...a),
}));

import Analysis from "./Analysis";

const options = {
  months: ["2026-04", "2026-05"],
  categories: ["Housing", "Groceries"],
  events: [],
};
const trend = {
  months: ["2026-04", "2026-05"],
  series: [
    { name: "Housing", values: [2000, 2000], total: 4000 },
    { name: "Groceries", values: [300, 250], total: 550 },
  ],
};

afterEach(() => vi.restoreAllMocks());

test("renders the Explore trend with sub-tabs and a filter bar", async () => {
  getFilterOptions.mockResolvedValue(options);
  getCategoryTrend.mockResolvedValue(trend);
  render(<Analysis />);

  await waitFor(() => expect(screen.getByText("Spending by category over time")).toBeInTheDocument());
  expect(screen.getByRole("tab", { name: "Explore" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Compare" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "People" })).toBeInTheDocument();
  expect(screen.getByLabelText("Filters")).toBeInTheDocument();
  // legend total from the trend
  expect(screen.getByText("$4,000.00")).toBeInTheDocument();
});

test("rollup toggle refetches with rollup=true", async () => {
  getFilterOptions.mockResolvedValue(options);
  getCategoryTrend.mockResolvedValue(trend);
  render(<Analysis />);

  await waitFor(() => expect(screen.getByText("Roll up to groups")).toBeInTheDocument());
  fireEvent.click(screen.getByText("Roll up to groups"));
  await waitFor(() =>
    expect(getCategoryTrend).toHaveBeenCalledWith(expect.objectContaining({ rollup: true })),
  );
});
