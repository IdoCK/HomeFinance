import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const setBudget = vi.fn().mockResolvedValue({ ok: true });
const deleteBudget = vi.fn().mockResolvedValue({ ok: true });
const getBudgets = vi.fn().mockResolvedValue([
  { id: 1, person_id: 1, category: "Groceries", amount: 400, budget: 400, spent: 312, expected_to_date: 252, projected_eom: 480, pct: 0.78, status: "ahead" },
  { id: 2, person_id: 1, category: "Rent", amount: 2000, budget: 2000, spent: 2000, expected_to_date: 1260, projected_eom: 2000, pct: 1.0, status: "over" },
]);

vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getBudgets: (...a: unknown[]) => getBudgets(...a),
  setBudget: (...a: unknown[]) => setBudget(...a),
  deleteBudget: (...a: unknown[]) => deleteBudget(...a),
}));

import Budgets from "./Budgets";

afterEach(() => { setBudget.mockClear(); deleteBudget.mockClear(); });

test("renders budgeted categories", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.getByText("Rent")).toBeInTheDocument();
});

test("editing a cap calls setBudget", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const cap = screen.getByDisplayValue("400");
  await userEvent.clear(cap);
  await userEvent.type(cap, "500");
  await userEvent.tab();
  expect(setBudget).toHaveBeenCalledWith({ personId: 1, category: "Groceries", amount: 500 });
});

test("removing a budget calls deleteBudget", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteBudget).toHaveBeenCalledWith(1);
});
