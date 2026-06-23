import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getOverview = vi.fn();
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({ getOverview: (...a: unknown[]) => getOverview(...a) }));

import Overview from "./Overview";

const base = {
  month: "2026-05", months: ["2026-04", "2026-05"],
  income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true,
  by_category: { Housing: 2000, Groceries: 300, "Eating out": 100 },
  alerts: [],
};

afterEach(() => vi.restoreAllMocks());

test("renders headline numbers and category breakdown", async () => {
  getOverview.mockResolvedValue(base);
  render(<Overview />);
  await waitFor(() => expect(screen.getByTestId("net")).toHaveTextContent("$2,600.00"));
  expect(screen.getByTestId("income")).toHaveTextContent("$5,000.00");
  expect(screen.getByTestId("spend")).toHaveTextContent("$2,400.00");
  expect(screen.getByText("52%")).toBeInTheDocument();
  expect(screen.getByText("Housing")).toBeInTheDocument();
});

test("renders spending alert chips", async () => {
  getOverview.mockResolvedValue({
    ...base,
    alerts: [{ category: "Eating out", current: 600, baseline: 100, delta: 500, pct: 150, direction: "up", new: false }],
  });
  render(<Overview />);
  await waitFor(() => expect(screen.getByLabelText("Spending alerts")).toBeInTheDocument());
  const alerts = within(screen.getByLabelText("Spending alerts"));
  expect(alerts.getByText("Eating out")).toBeInTheDocument();
  expect(alerts.getByText(/150% vs usual/)).toBeInTheDocument();
});
