import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const getOverview = vi.fn();
const getNetWorth = vi.fn();
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
  getActiveCurrency: () => "USD",
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({
  getOverview: (...a: unknown[]) => getOverview(...a),
  getNetWorth: (...a: unknown[]) => getNetWorth(...a),
}));

import Overview from "./Overview";

beforeEach(() => {
  // Default: no net-worth trend, so the contributions-vs-net-worth overlay
  // stays hidden unless a test opts in.
  getNetWorth.mockResolvedValue({ summary: { assets: 0, liabilities: 0, net: 0 }, delta: null, accounts: [], trend: [], split: null });
});

const base = {
  month: "2026-05", months: ["2026-04", "2026-05"],
  income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true,
  by_category: { Housing: 2000, Groceries: 300, "Eating out": 100 },
  alerts: [],
  uncategorized: { count: 0, amount: 0 },
  safe_to_spend: 4685, committed: 15, committed_spent: 15, discretionary_spent: 300,
  bills_due: { count: 0, amount: 0 },
};

afterEach(() => vi.clearAllMocks());

test("renders headline numbers and category breakdown", async () => {
  getOverview.mockResolvedValue(base);
  render(<Overview />);
  await waitFor(() => expect(screen.getByTestId("net")).toHaveTextContent("$2,600.00"));
  expect(screen.getByTestId("income")).toHaveTextContent("$5,000.00");
  expect(screen.getByTestId("spend")).toHaveTextContent("$2,400.00");
  expect(screen.getByText("52%")).toBeInTheDocument();
  expect(screen.getAllByText("Housing").length).toBeGreaterThan(0);
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

test("savings-rate card shows the FIRE benchmark line and a verdict", async () => {
  getOverview.mockResolvedValue({
    ...base,
    series: [
      { month: "2026-03", income: 5000, spend: 2500, net: 2500, savings_rate: 0.50, complete: true },
      { month: "2026-04", income: 5000, spend: 2500, net: 2500, savings_rate: 0.50, complete: true },
      { month: "2026-05", income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true },
    ],
  });
  render(<Overview />);
  // The verdict and the chart's accessible benchmark description both render
  // outside Recharts' (jsdom-empty) plot area.
  await waitFor(() => expect(screen.getByText(/FIRE pace/i)).toBeInTheDocument());
  expect(screen.getByText(/against 20% and 50%/i)).toBeInTheDocument();
});

test("Trend view overlays contributions against net worth (the gap = returns)", async () => {
  getOverview.mockResolvedValue({
    ...base,
    series: [
      { month: "2026-01", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
      { month: "2026-02", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
      { month: "2026-03", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
    ],
  });
  // Net worth grows faster than the $1,000/mo contributions — the extra is returns.
  getNetWorth.mockResolvedValue({
    summary: { assets: 24000, liabilities: 0, net: 24000 }, delta: null, accounts: [], split: null,
    trend: [
      { date: "2026-01-31", assets: 20000, liabilities: 0, net: 20000 },
      { date: "2026-02-28", assets: 22000, liabilities: 0, net: 22000 },
      { date: "2026-03-31", assets: 24000, liabilities: 0, net: 24000 },
    ],
  });
  render(<Overview />, { wrapper: MemoryRouter });
  await waitFor(() => expect(screen.getByTestId("net")).toBeInTheDocument());
  // Switch the cash-flow card to the Trend view.
  await userEvent.click(screen.getByRole("button", { name: "Trend" }));
  // The contributions-vs-net-worth overlay appears with both series and a
  // returns/appreciation read-out of the gap.
  const overlay = await screen.findByLabelText(/contributions vs(\.)? net worth/i);
  // Both series are present in the legend, and the gap is read out as returns.
  expect(within(overlay).getAllByText(/net worth/i).length).toBeGreaterThanOrEqual(1);
  expect(within(overlay).getAllByText(/contributions/i).length).toBeGreaterThanOrEqual(1);
  expect(within(overlay).getByText(/returns & appreciation/i)).toBeInTheDocument();
  // The $2,000 gap (24,000 net worth − 22,000 contributed) is surfaced.
  expect(within(overlay).getByText(/\$2,000/)).toBeInTheDocument();
});

test("Trend view hides the net-worth overlay without enough snapshots", async () => {
  getOverview.mockResolvedValue({
    ...base,
    series: [
      { month: "2026-01", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
      { month: "2026-02", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
    ],
  });
  // Only a single snapshot — not enough to draw a trend.
  getNetWorth.mockResolvedValue({
    summary: { assets: 20000, liabilities: 0, net: 20000 }, delta: null, accounts: [], split: null,
    trend: [{ date: "2026-02-28", assets: 20000, liabilities: 0, net: 20000 }],
  });
  render(<Overview />, { wrapper: MemoryRouter });
  await waitFor(() => expect(screen.getByTestId("net")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Trend" }));
  expect(screen.queryByLabelText(/contributions vs(\.)? net worth/i)).toBeNull();
});

test("AI insights card leads with an insight, not a duplicate net", async () => {
  getOverview.mockResolvedValue({
    ...base,
    alerts: [{ category: "Eating out", current: 600, baseline: 100, delta: 500, pct: 150, direction: "up", new: false }],
  });
  render(<Overview />);
  const ai = await screen.findByLabelText("AI insights");
  // The card leads with the insight (the month's biggest spending shift)…
  expect(within(ai).getAllByText(/eating out/i).length).toBeGreaterThanOrEqual(1);
  expect(within(ai).getByText(/versus your usual/i)).toBeInTheDocument();
  // …and never repeats the net figure.
  expect(within(ai).queryByText(/2,600/)).toBeNull();
});

test("single-persona view shows a ranked category bar with amounts", async () => {
  getOverview.mockResolvedValue(base); // single persona: no split
  render(<Overview />);
  await waitFor(() => expect(screen.getByText("Top categories")).toBeInTheDocument());
  const card = screen.getByText("Top categories").closest("section") as HTMLElement;
  // Ranked bar (StackedBars) shows each category with its amount.
  expect(within(card).getByText("Housing")).toBeInTheDocument();
  expect(within(card).getByText("$2,000.00")).toBeInTheDocument();
});

test("Joint view keeps the who-spent-what dot matrix", async () => {
  getOverview.mockResolvedValue({
    ...base,
    split: [
      { person_id: 1, name: "Ido", spend: 1500 },
      { person_id: 2, name: "Aviv", spend: 900 },
    ],
  });
  render(<Overview />);
  await waitFor(() => expect(screen.getByText("Who spent what")).toBeInTheDocument());
  const card = screen.getByText("Who spent what").closest("section") as HTMLElement;
  expect(within(card).getByText("Ido")).toBeInTheDocument();
  expect(within(card).getByText("Aviv")).toBeInTheDocument();
});

test("Trend view links out to Analysis for deeper trends", async () => {
  getOverview.mockResolvedValue({
    ...base,
    series: [
      { month: "2026-04", income: 4000, spend: 3000, net: 1000, savings_rate: 0.25, complete: true },
      { month: "2026-05", income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true },
    ],
  });
  render(<Overview />, { wrapper: MemoryRouter });
  await waitFor(() => expect(screen.getByTestId("net")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Trend" }));
  const link = await screen.findByRole("link", { name: /compare months & categories in analysis/i });
  expect(link).toHaveAttribute("href", "/analysis");
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
