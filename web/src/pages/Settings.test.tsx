import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const renamePerson = vi.fn().mockResolvedValue({ id: 1, name: "Adelaide" });
const getPeople = vi.fn().mockResolvedValue([{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }]);
const upsertCategory = vi.fn().mockResolvedValue({ ok: true });
const deleteCategory = vi.fn().mockResolvedValue({ ok: true });
const upsertVendor = vi.fn().mockResolvedValue({ ok: true });
const deleteVendor = vi.fn().mockResolvedValue({ ok: true });
const getCategories = vi.fn().mockResolvedValue([{ id: 10, person_id: 1, name: "Groceries", keywords: "whole foods" }]);
const getVendors = vi.fn().mockResolvedValue([{ id: 20, person_id: 1, name: "Amazon", keywords: "amazon,amzn" }]);
const getFxRates = vi.fn().mockResolvedValue({ source: null, last_fetched: null, count: 0, rates: [] });

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
  getPeople: (...a: unknown[]) => getPeople(...a),
  renamePerson: (...a: unknown[]) => renamePerson(...a),
  getCategories: (...a: unknown[]) => getCategories(...a),
  upsertCategory: (...a: unknown[]) => upsertCategory(...a),
  deleteCategory: (...a: unknown[]) => deleteCategory(...a),
  getVendors: (...a: unknown[]) => getVendors(...a),
  upsertVendor: (...a: unknown[]) => upsertVendor(...a),
  deleteVendor: (...a: unknown[]) => deleteVendor(...a),
  getFxRates: (...a: unknown[]) => getFxRates(...a),
}));

import Settings from "./Settings";

afterEach(() => {
  renamePerson.mockClear(); upsertCategory.mockClear(); deleteCategory.mockClear();
  upsertVendor.mockClear(); deleteVendor.mockClear();
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
