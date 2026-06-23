import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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
  uncategorized: { count: 0, amount: 0 },
  safe_to_spend: 4685, committed: 15, committed_spent: 15, discretionary_spent: 300,
  bills_due: { count: 0, amount: 0 },
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
  // Safe-to-spend hero leads the page with the present-month answer.
  expect(screen.getByTestId("safe-to-spend")).toHaveTextContent("$4,685.00");
  // The "This month" spend bar splits committed vs discretionary.
  expect(screen.getByText("Committed")).toBeInTheDocument();
  expect(screen.getByText("Discretionary")).toBeInTheDocument();
});

test("partial month: shows an in-progress banner and guards the MoM delta", async () => {
  getOverview.mockResolvedValue({
    ...base,
    complete: false,
    series: [
      { month: "2026-04", income: 4000, spend: 3000, net: 1000, savings_rate: 0.25, complete: true },
      { month: "2026-05", income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: false },
    ],
  });
  render(<Overview />);
  // A partial-month notice appears (text differs for current vs past partial month).
  await waitFor(() => expect(screen.getByText(/in progress|partial month/i)).toBeInTheDocument());
  // The trend arrow must NOT render when a month in the comparison is incomplete…
  expect(screen.queryByText(/▲|▼/)).toBeNull();
  // …it is replaced by an explicit "(partial)" affordance instead.
  expect(screen.getByText(/vs last month/i)).toBeInTheDocument();
});

test("complete month: shows a trend arrow, no partial banner", async () => {
  getOverview.mockResolvedValue({
    ...base,
    complete: true,
    series: [
      { month: "2026-04", income: 4000, spend: 3000, net: 1000, savings_rate: 0.25, complete: true },
      { month: "2026-05", income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true },
    ],
  });
  render(<Overview />);
  await waitFor(() => expect(screen.getByText(/▲|▼/)).toBeInTheDocument());
  expect(screen.queryByText(/in progress/i)).toBeNull();
});

test("promotes a prominent monthly verdict", async () => {
  getOverview.mockResolvedValue(base); // net positive, complete
  render(<Overview />);
  await waitFor(() => expect(screen.getByText(/in the black/i)).toBeInTheDocument());
});

test("negative net shows a warning verdict", async () => {
  getOverview.mockResolvedValue({ ...base, net: -200 });
  render(<Overview />);
  await waitFor(() => expect(screen.getByText(/outpacing income/i)).toBeInTheDocument());
});

test("shows an uncategorized badge linking to a filtered Transactions view", async () => {
  getOverview.mockResolvedValue({ ...base, uncategorized: { count: 4, amount: 130 } });
  render(<Overview />, { wrapper: MemoryRouter });
  await waitFor(() => expect(screen.getByText(/uncategorized/i)).toBeInTheDocument());
  const link = screen.getByRole("link", { name: /uncategorized/i });
  expect(link).toHaveAttribute("href", "/transactions?category=Uncategorized");
});

test("summarizes bills still due this month when any are pending", async () => {
  getOverview.mockResolvedValue({ ...base, bills_due: { count: 3, amount: 250 } });
  render(<Overview />);
  await waitFor(() => expect(screen.getByText(/still due this month/i)).toBeInTheDocument());
  expect(screen.getByText(/3 bills/i)).toBeInTheDocument();
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
