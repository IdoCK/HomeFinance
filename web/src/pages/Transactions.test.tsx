import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const updateTransaction = vi.fn().mockResolvedValue({});
const getTransactions = vi.fn();
const getTransferPairs = vi.fn();

const ROWS = [
  { id: 1, person_id: 1, date: "2026-05-02", description: "Trader Joes", amount: -84.2, category: "Groceries", source: "card", included: 1, balance: null, person: "Ada" },
  { id: 2, person_id: 1, date: "2026-05-03", description: "Paycheck", amount: 5000, category: "Income", source: "bank", included: 1, balance: null, person: "Ada" },
  { id: 3, person_id: 1, date: "2026-05-05", description: "Netflix", amount: -15.99, category: "Subscriptions", source: "card", included: 1, balance: null, person: "Ada" },
];

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getTransactions: (...a: unknown[]) => getTransactions(...a),
  getTransferPairs: (...a: unknown[]) => getTransferPairs(...a),
  updateTransaction: (...args: unknown[]) => updateTransaction(...args),
}));

import Transactions from "./Transactions";

beforeEach(() => {
  getTransactions.mockResolvedValue(ROWS);
  getTransferPairs.mockResolvedValue([]);
});
afterEach(() => { updateTransaction.mockClear(); getTransactions.mockReset(); getTransferPairs.mockReset(); });

test("renders the persona's transactions", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  expect(screen.getByText("Paycheck")).toBeInTheDocument();
  expect(screen.getByText("Netflix")).toBeInTheDocument();
});

test("search filters rows by description", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText(/search/i), "netflix");
  expect(screen.queryByText("Trader Joes")).not.toBeInTheDocument();
  expect(screen.getByText("Netflix")).toBeInTheDocument();
});

test("editing a category calls updateTransaction", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  const input = screen.getByDisplayValue("Subscriptions");
  await userEvent.clear(input);
  await userEvent.type(input, "Streaming");
  await userEvent.tab();
  expect(updateTransaction).toHaveBeenCalledWith(3, { category: "Streaming" });
});

test("toggling Included calls updateTransaction", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  const toggles = screen.getAllByRole("checkbox");
  await userEvent.click(toggles[0]);
  expect(updateTransaction).toHaveBeenCalledWith(1, { included: false });
});

test("transfer-pair banner excludes both sides", async () => {
  getTransferPairs.mockResolvedValueOnce([
    { amount: 500, out_id: 2, in_id: 1, out_date: "2026-05-01", in_date: "2026-05-02",
      out_desc: "Zelle out", in_desc: "Zelle in", out_person: 1, in_person: 2,
      days_apart: 1, cross_person: true, both_included: true },
  ]);
  render(<Transactions />);
  await waitFor(() => expect(screen.getByLabelText("Transfer pairs")).toBeInTheDocument());
  expect(screen.getByText(/1 transfer pair detected/i)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /exclude both/i }));
  expect(updateTransaction).toHaveBeenCalledWith(2, { included: false });
  expect(updateTransaction).toHaveBeenCalledWith(1, { included: false });
});
