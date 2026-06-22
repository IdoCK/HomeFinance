import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addAccount = vi.fn().mockResolvedValue({ ok: true, id: 9 });
const updateAccountBalance = vi.fn().mockResolvedValue({ ok: true });
const deleteAccount = vi.fn().mockResolvedValue({ ok: true });
const getReconciliation = vi.fn().mockResolvedValue({ reconcilable: false });
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
  addAccount: (...a: unknown[]) => addAccount(...a),
  updateAccountBalance: (...a: unknown[]) => updateAccountBalance(...a),
  deleteAccount: (...a: unknown[]) => deleteAccount(...a),
  getReconciliation: (...a: unknown[]) => getReconciliation(...a),
}));

import NetWorth from "./NetWorth";

afterEach(() => { addAccount.mockClear(); updateAccountBalance.mockClear(); deleteAccount.mockClear(); getReconciliation.mockClear(); mockPersonId = 1; });

test("renders the net worth total and accounts", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toHaveTextContent("$25,000.00"));
  expect(screen.getByText("Vanguard")).toBeInTheDocument();
  expect(screen.getByText("Visa")).toBeInTheDocument();
});

test("shows the reconciliation panel when statements tie out", async () => {
  getReconciliation.mockResolvedValueOnce({
    reconcilable: true, ok: true, begin: 1000, end: 1300, sum_amounts: 300,
    computed_end: 1300, discrepancy: 0, n: 2, chain_breaks: 0,
  });
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByLabelText("Statement reconciliation")).toBeInTheDocument());
  expect(screen.getByText(/statements tie out/i)).toBeInTheDocument();
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
