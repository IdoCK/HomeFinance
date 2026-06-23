import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addGoal = vi.fn().mockResolvedValue({ ok: true });
const updateGoalSaved = vi.fn().mockResolvedValue({ ok: true });
const updateGoalNotes = vi.fn().mockResolvedValue({ ok: true });
const deleteGoal = vi.fn().mockResolvedValue({ ok: true });
const getGoals = vi.fn().mockResolvedValue([
  { id: 1, person_id: 1, name: "Emergency fund", target_amount: 10000, saved_amount: 2500, target_date: "2026-12-31", horizon: "short", notes: "", percent: 25, monthly_needed: 1250 },
  { id: 2, person_id: 1, name: "Vacation", target_amount: 5000, saved_amount: 5000, target_date: null, horizon: "short", notes: "", percent: 100, monthly_needed: null },
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
  getGoals: (...a: unknown[]) => getGoals(...a),
  addGoal: (...a: unknown[]) => addGoal(...a),
  updateGoalSaved: (...a: unknown[]) => updateGoalSaved(...a),
  updateGoalNotes: (...a: unknown[]) => updateGoalNotes(...a),
  deleteGoal: (...a: unknown[]) => deleteGoal(...a),
}));

import Goals from "./Goals";

afterEach(() => { addGoal.mockClear(); updateGoalSaved.mockClear(); updateGoalNotes.mockClear(); deleteGoal.mockClear(); });

test("renders goals with progress", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  expect(screen.getByText("Vacation")).toBeInTheDocument();
});

test("editing saved calls updateGoalSaved", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  const saved = screen.getByDisplayValue("2500");
  await userEvent.clear(saved);
  await userEvent.type(saved, "3000");
  await userEvent.tab();
  expect(updateGoalSaved).toHaveBeenCalledWith(1, 3000);
});

test("shows the horizon badge and saves edited notes", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  expect(screen.getAllByText("short-term").length).toBeGreaterThan(0);
  const note = screen.getByLabelText("Notes for Emergency fund");
  await userEvent.type(note, "3 months runway");
  await userEvent.tab();
  expect(updateGoalNotes).toHaveBeenCalledWith(1, "3 months runway");
});

test("removing a goal calls deleteGoal", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteGoal).toHaveBeenCalledWith(1);
});
