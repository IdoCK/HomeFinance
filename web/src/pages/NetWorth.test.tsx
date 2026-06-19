import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addAccount = vi.fn().mockResolvedValue({ ok: true, id: 9 });
const updateAccountBalance = vi.fn().mockResolvedValue({ ok: true });
const deleteAccount = vi.fn().mockResolvedValue({ ok: true });
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

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getNetWorth: (...a: unknown[]) => getNetWorth(...a),
  addAccount: (...a: unknown[]) => addAccount(...a),
  updateAccountBalance: (...a: unknown[]) => updateAccountBalance(...a),
  deleteAccount: (...a: unknown[]) => deleteAccount(...a),
}));

import NetWorth from "./NetWorth";

afterEach(() => { addAccount.mockClear(); updateAccountBalance.mockClear(); deleteAccount.mockClear(); });

test("renders the net worth total and accounts", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toHaveTextContent("$25,000.00"));
  expect(screen.getByText("Vanguard")).toBeInTheDocument();
  expect(screen.getByText("Visa")).toBeInTheDocument();
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
