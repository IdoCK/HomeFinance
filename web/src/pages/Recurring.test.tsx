import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getRecurring = vi.fn().mockResolvedValue({
  charges: [
    { vendor: "Netflix", category: "Subscriptions", cadence: "monthly", kind: "fixed", typical_amount: 15.99, prior_typical: 15.99, prior_stable: true, first_date: "2026-01-05", last_date: "2026-06-05", last_amount: 15.99, next_expected: "2026-07-05", count: 6, monthly_cost: 15.99, annual_cost: 191.88, confidence: 0.95 },
    { vendor: "Comcast", category: "Utilities", cadence: "monthly", kind: "variable", typical_amount: 89, prior_typical: 85, prior_stable: true, first_date: "2026-01-10", last_date: "2026-06-10", last_amount: 102, next_expected: "2026-07-10", count: 6, monthly_cost: 89, annual_cost: 1068, confidence: 0.8 },
  ],
  committed: { fixed: 15.99, variable: 89, total: 104.99 },
  anomalies: [{ vendor: "Comcast", type: "price_change", detail: "85.00 -> 102.00", pct: 20 }],
});

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "joint", personId: undefined, label: "Joint", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({ getRecurring: (...a: unknown[]) => getRecurring(...a) }));

import Recurring from "./Recurring";

afterEach(() => getRecurring.mockClear());

test("renders detected subscriptions", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  expect(screen.getByText("Comcast")).toBeInTheDocument();
});

test("shows the committed monthly total", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByTestId("committed-total")).toHaveTextContent("$104.99"));
});

test("surfaces a price-change anomaly", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  expect(screen.getByText(/price change/i)).toBeInTheDocument();
});
