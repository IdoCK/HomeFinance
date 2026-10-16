import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const renamePerson = vi.fn().mockResolvedValue({ id: 1, name: "Adelaide" });
const getPeople = vi.fn().mockResolvedValue([{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }]);
const upsertCategory = vi.fn().mockResolvedValue({ ok: true });
const deleteCategory = vi.fn().mockResolvedValue({ ok: true });
const upsertVendor = vi.fn().mockResolvedValue({ ok: true });
const deleteVendor = vi.fn().mockResolvedValue({ ok: true });
const getCategories = vi.fn().mockResolvedValue([{ id: 10, name: "Groceries", keywords: "whole foods" }]);
const getVendors = vi.fn().mockResolvedValue([{ id: 20, name: "Amazon", keywords: "amazon,amzn" }]);
const getDisplayRate = vi.fn().mockResolvedValue({ base: "USD", quote: "ILS", rate: 3.7, source: "seed" });
const setDisplayRate = vi.fn().mockResolvedValue({ ok: true, rate: 3.7 });
const refreshDisplayRate = vi.fn().mockResolvedValue({ ok: true, rate: 3.7 });
const getUntrackedCount = vi.fn().mockResolvedValue({ count: 0 });

vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
  getActiveCurrency: () => "USD",
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getPeople: (...a: unknown[]) => getPeople(...a),
  renamePerson: (...a: unknown[]) => renamePerson(...a),
  getCategories: (...a: unknown[]) => getCategories(...a),
  upsertCategory: (...a: unknown[]) => upsertCategory(...a),
  deleteCategory: (...a: unknown[]) => deleteCategory(...a),
  getVendors: (...a: unknown[]) => getVendors(...a),
  upsertVendor: (...a: unknown[]) => upsertVendor(...a),
  deleteVendor: (...a: unknown[]) => deleteVendor(...a),
  getDisplayRate: (...a: unknown[]) => getDisplayRate(...a),
  setDisplayRate: (...a: unknown[]) => setDisplayRate(...a),
  refreshDisplayRate: (...a: unknown[]) => refreshDisplayRate(...a),
  getUntrackedCount: (...a: unknown[]) => getUntrackedCount(...a),
}));

import Settings from "./Settings";
import { getAssumedReturn } from "@/lib/prefs";

afterEach(() => {
  renamePerson.mockClear(); upsertCategory.mockClear(); deleteCategory.mockClear();
  upsertVendor.mockClear(); deleteVendor.mockClear();
});

test("editing the assumed annual return persists it for projections", async () => {
  render(<Settings />);
  const input = await screen.findByLabelText("Assumed annual return percent");
  await userEvent.clear(input);
  await userEvent.type(input, "9");
  await userEvent.tab();
  expect(getAssumedReturn()).toBeCloseTo(0.09, 5);
});

test("surfaces an untracked-row audit banner when legacy rows exist", async () => {
  getUntrackedCount.mockResolvedValueOnce({ count: 42 });
  render(<Settings />);
  expect(await screen.findByText(/predate file tracking/i)).toBeInTheDocument();
  expect(screen.getByText("42")).toBeInTheDocument();
});

test("hides the audit banner when there are no untracked rows", async () => {
  render(<Settings />); // default mock: count 0
  await waitFor(() => expect(screen.getByText(/Money/i)).toBeInTheDocument());
  expect(screen.queryByText(/predate file tracking/i)).toBeNull();
});

test("renders a Money section with a currency control", async () => {
  render(<Settings />);
  expect(await screen.findByText(/Money/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /USD/ })).toBeInTheDocument();
});

test("renders categories and vendors for the active person", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.getByText("Amazon")).toBeInTheDocument();
});

test("renaming a person calls renamePerson", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByDisplayValue("Ada")).toBeInTheDocument());
  const input = screen.getByDisplayValue("Ada");
  await userEvent.clear(input);
  await userEvent.type(input, "Adelaide");
  await userEvent.tab();
  expect(renamePerson).toHaveBeenCalledWith(1, "Adelaide");
});

test("adding a category calls upsertCategory", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText("New category name"), "Travel");
  await userEvent.type(screen.getByPlaceholderText("Category keywords"), "airbnb,delta");
  await userEvent.click(screen.getByRole("button", { name: /add category/i }));
  expect(upsertCategory).toHaveBeenCalledWith({ personId: 1, name: "Travel", keywords: "airbnb,delta" });
});

test("deleting a category calls deleteCategory", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: /remove category Groceries/i }));
  expect(deleteCategory).toHaveBeenCalledWith(10);
});

test("assigning a parent group calls upsertCategory with the parent (keywords preserved)", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const parent = screen.getByLabelText("Parent group for category Groceries");
  await userEvent.type(parent, "Essentials");
  await userEvent.tab();
  expect(upsertCategory).toHaveBeenCalledWith({ personId: 1, name: "Groceries", keywords: "whole foods", parent: "Essentials" });
});

test("categories panel renders rows from getCategories as a shared list", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.getByLabelText("Keywords for category Groceries")).toBeInTheDocument();
  // Both Categories and Vendor groups panels show the shared caption
  expect(screen.getAllByText("Shared across everyone")).toHaveLength(2);
});

test("editing keywords in the categories panel calls upsertCategory", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const kwInput = screen.getByLabelText("Keywords for category Groceries");
  await userEvent.clear(kwInput);
  await userEvent.type(kwInput, "trader joes");
  await userEvent.tab();
  expect(upsertCategory).toHaveBeenCalledWith({ personId: 1, name: "Groceries", keywords: "trader joes" });
});

test("per-person picker is not rendered in the categories/vendor panels", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.queryByText(/Editing rules for/i)).toBeNull();
});
