import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addAccount = vi.fn().mockResolvedValue({ ok: true, id: 9 });
const updateAccountBalance = vi.fn().mockResolvedValue({ ok: true });
const deleteAccount = vi.fn().mockResolvedValue({ ok: true });
const getReconciliation = vi.fn().mockResolvedValue({ statements: [] });
const getAccountHistory = vi.fn().mockResolvedValue({ snapshots: [] });
const getAccountImports = vi.fn().mockResolvedValue({ imports: [] });
const recordAccountSnapshot = vi.fn().mockResolvedValue({ ok: true });
const populateFromStatements = vi.fn().mockResolvedValue({ ok: true, recorded: 2 });
const getNetWorthProjection = vi.fn().mockResolvedValue({ annual_return: 0.07, monthly_savings: 0, current_net: 25000, points: [] });
const NO_GROWTH = {
  current_net: 25000, trailing_abs: null, trailing_pct: null, cagr: null, span_years: null,
  fire_number: null, pct_to_fire: null, runway_months: null, monthly_expenses: 0, monthly_committed: 0,
};
const getNetWorthGrowth = vi.fn().mockResolvedValue(NO_GROWTH);
const getNetWorth = vi.fn().mockResolvedValue({
  summary: { assets: 30000, liabilities: 5000, net: 25000 },
  delta: 2000,
  accounts: [
    { id: 1, person_id: 1, name: "Vanguard", kind: "investment", is_asset: 1, balance: 30000, updated_at: "2026-06-19" },
    { id: 2, person_id: 1, name: "Visa", kind: "credit_card", is_asset: 0, balance: 5000, updated_at: "2026-06-19" },
  ],
  trend: [
    { date: "2026-01-01", assets: 28000, liabilities: 5000, net: 23000 },
    { date: "2026-06-19", assets: 30000, liabilities: 5000, net: 25000 },
  ],
});

vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
  getActiveCurrency: () => "USD",
}));
let mockPersonId: number | undefined = 1;
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: mockPersonId == null ? "joint" : "you",
    personId: mockPersonId,
    label: mockPersonId == null ? "Joint" : "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getNetWorth: (...a: unknown[]) => getNetWorth(...a),
  getNetWorthProjection: (...a: unknown[]) => getNetWorthProjection(...a),
  getNetWorthGrowth: (...a: unknown[]) => getNetWorthGrowth(...a),
  addAccount: (...a: unknown[]) => addAccount(...a),
  updateAccountBalance: (...a: unknown[]) => updateAccountBalance(...a),
  deleteAccount: (...a: unknown[]) => deleteAccount(...a),
  getReconciliation: (...a: unknown[]) => getReconciliation(...a),
  getAccountHistory: (...a: unknown[]) => getAccountHistory(...a),
  getAccountImports: (...a: unknown[]) => getAccountImports(...a),
  recordAccountSnapshot: (...a: unknown[]) => recordAccountSnapshot(...a),
  populateFromStatements: (...a: unknown[]) => populateFromStatements(...a),
}));

import NetWorth from "./NetWorth";

afterEach(() => { addAccount.mockClear(); updateAccountBalance.mockClear(); deleteAccount.mockClear(); getReconciliation.mockClear(); getAccountHistory.mockReset(); getAccountHistory.mockResolvedValue({ snapshots: [] }); getAccountImports.mockClear(); recordAccountSnapshot.mockClear(); populateFromStatements.mockClear(); getNetWorthProjection.mockClear(); getNetWorthProjection.mockResolvedValue({ annual_return: 0.07, monthly_savings: 0, current_net: 25000, points: [] }); getNetWorthGrowth.mockReset(); getNetWorthGrowth.mockResolvedValue(NO_GROWTH); mockPersonId = 1; });

test("renders the net worth total and accounts", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toHaveTextContent("$25,000.00"));
  expect(screen.getByText("Vanguard")).toBeInTheDocument();
  expect(screen.getByText("Visa")).toBeInTheDocument();
});

test("net-worth trend renders a chart once there are 2+ snapshots", async () => {
  getNetWorth.mockResolvedValueOnce({
    summary: { assets: 320000, liabilities: 20000, net: 300000 }, delta: 5000,
    accounts: [],
    trend: [
      { date: "2026-01-01", assets: 130000, liabilities: 10000, net: 120000 },
      { date: "2026-06-19", assets: 320000, liabilities: 20000, net: 300000 },
    ],
  });
  const { container } = render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toBeInTheDocument());
  // With two snapshots the trend chart renders instead of the empty-state prompt.
  // (Axis labels + milestone lines are now Recharts internals, not asserted in jsdom.)
  expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  expect(screen.queryByText(/add a second snapshot/i)).toBeNull();
});

test("renders a net-worth projection card (with vs without returns)", async () => {
  getNetWorthProjection.mockResolvedValueOnce({
    annual_return: 0.07, monthly_savings: 2000, current_net: 25000,
    points: Array.from({ length: 120 }, (_, i) => ({ month: i + 1, linear: 25000 + 2000 * (i + 1), compounding: 25000 + 2200 * (i + 1) })),
  });
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByLabelText("Net worth projection")).toBeInTheDocument());
  expect(screen.getByTestId("projection-headline")).toHaveTextContent("in 10 years");
  expect(screen.getByText(/7% assumed return/i)).toBeInTheDocument();
});

test("renders wealth stats: trailing 12m, CAGR, FIRE progress and runway", async () => {
  getNetWorthGrowth.mockResolvedValueOnce({
    current_net: 130000, trailing_abs: 30000, trailing_pct: 30, cagr: 0.12, span_years: 2,
    fire_number: 900000, pct_to_fire: 0.1444, runway_months: 10, monthly_expenses: 3000, monthly_committed: 2500,
  });
  render(<NetWorth />);
  const strip = await screen.findByLabelText("Wealth stats");
  // Trailing 12-month growth (dollars + percent).
  expect(within(strip).getByText(/past 12 months/i)).toBeInTheDocument();
  expect(within(strip).getByText(/\$30,000/)).toBeInTheDocument();
  expect(within(strip).getByText(/30%/)).toBeInTheDocument();
  // CAGR.
  expect(within(strip).getByText(/12%/)).toBeInTheDocument();
  // FIRE progress: 14% of the 25x target.
  expect(within(strip).getByText(/FIRE/i)).toBeInTheDocument();
  expect(within(strip).getByText(/14%/)).toBeInTheDocument();
  // Runway in months.
  expect(within(strip).getByText("Runway")).toBeInTheDocument();
  expect(within(strip).getByText(/10 mo/)).toBeInTheDocument();
});

test("hides the wealth-stats strip when there is nothing to show", async () => {
  // Default mock = all nulls.
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toBeInTheDocument());
  expect(screen.queryByLabelText("Wealth stats")).toBeNull();
});

test("renders a per-account balance sparkline when history has 2+ snapshots", async () => {
  getAccountHistory.mockResolvedValue({
    snapshots: [
      { date: "2026-01-01", balance: 28000 },
      { date: "2026-06-19", balance: 30000 },
    ],
  });
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  expect(await screen.findByLabelText("Vanguard balance history")).toBeInTheDocument();
});

test("Manage panel records a manual as-of-date snapshot", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Manage Vanguard" }));
  await userEvent.type(screen.getByLabelText("Snapshot date for Vanguard"), "2026-03-31");
  await userEvent.type(screen.getByLabelText("Snapshot balance for Vanguard"), "31000");
  await userEvent.click(screen.getByRole("button", { name: "Record balance" }));
  expect(recordAccountSnapshot).toHaveBeenCalledWith(1, "2026-03-31", 31000);
});

test("Manage panel populates month-end balances from a picked statement", async () => {
  getAccountImports.mockResolvedValueOnce({ imports: [{ file_hash: "h1", filename: "april.csv", count: 12 }] });
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Manage Vanguard" }));
  await userEvent.click(await screen.findByLabelText("Use april.csv"));
  await userEvent.click(screen.getByRole("button", { name: "Populate" }));
  expect(populateFromStatements).toHaveBeenCalledWith(1, ["h1"]);
});

test("shows a reconciliation card per statement when statements tie out", async () => {
  getReconciliation.mockResolvedValueOnce({
    statements: [
      {
        filename: "bank.csv", currency: "USD",
        ok: true, begin: 1000, end: 1300, sum_amounts: 300,
        computed_end: 1300, discrepancy: 0, n: 2, chain_breaks: 0,
      },
    ],
  });
  render(<NetWorth />);
  await waitFor(() =>
    expect(screen.getByLabelText("Statement reconciliation: bank.csv")).toBeInTheDocument()
  );
  expect(screen.getByText(/ties out/i)).toBeInTheDocument();
});

test("editing a balance calls updateAccountBalance", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  const bal = screen.getByDisplayValue("30000");
  await userEvent.clear(bal);
  await userEvent.type(bal, "31000");
  await userEvent.tab();
  expect(updateAccountBalance).toHaveBeenCalledWith(1, 31000);
});

test("removing an account calls deleteAccount", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteAccount).toHaveBeenCalledWith(1);
});

test("shows household breakdown rows in Joint view", async () => {
  mockPersonId = undefined;
  getNetWorth.mockResolvedValueOnce({
    summary: { assets: 5000, liabilities: 0, net: 5000 }, delta: null, accounts: [], trend: [],
    split: [
      { person_id: 2, name: "Ido", net: 1000, assets: 1000, liabilities: 0 },
      { person_id: 1, name: "Aviv", net: 4000, assets: 4000, liabilities: 0 },
    ],
  });
  render(<NetWorth />);
  const panel = await screen.findByLabelText("Household breakdown");
  expect(within(panel).getByText("Ido")).toBeInTheDocument();
  expect(within(panel).getByText("Aviv")).toBeInTheDocument();
});
