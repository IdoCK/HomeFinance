import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const updateTransaction = vi.fn().mockResolvedValue({});

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getTransactions: vi.fn().mockResolvedValue([
    { id: 1, person_id: 1, date: "2026-05-02", description: "Trader Joes", amount: -84.2, category: "Groceries", source: "card", included: 1, balance: null, person: "Ada" },
    { id: 2, person_id: 1, date: "2026-05-03", description: "Paycheck", amount: 5000, category: "Income", source: "bank", included: 1, balance: null, person: "Ada" },
    { id: 3, person_id: 1, date: "2026-05-05", description: "Netflix", amount: -15.99, category: "Subscriptions", source: "card", included: 1, balance: null, person: "Ada" },
  ]),
  updateTransaction: (...args: unknown[]) => updateTransaction(...args),
}));

import Transactions from "./Transactions";

afterEach(() => updateTransaction.mockClear());

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
