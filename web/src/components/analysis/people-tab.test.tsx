import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getOverlap = vi.fn();
vi.mock("@/lib/api", () => ({ getOverlap: (...a: unknown[]) => getOverlap(...a) }));
vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
  getActiveCurrency: () => "USD",
}));

import { PeopleTab } from "./people-tab";

afterEach(() => vi.restoreAllMocks());

test("shows per-person totals, shared count and the diverging rows", async () => {
  getOverlap.mockResolvedValue({
    available: true,
    a: { id: 1, name: "Ido", spend: 2300, categories: 2 },
    b: { id: 2, name: "Aviv", spend: 150, categories: 2 },
    shared: 1,
    rows: [
      { category: "Housing", a: 2000, b: 0, diff: 2000, shared: false },
      { category: "Groceries", a: 300, b: 100, diff: 200, shared: true },
      { category: "Dining", a: 0, b: 50, diff: -50, shared: true },
    ],
  });
  render(<PeopleTab filters={{}} />);

  await waitFor(() => expect(screen.getByText("$2,300.00")).toBeInTheDocument());
  expect(screen.getByText("Ido spent")).toBeInTheDocument();
  expect(screen.getByText("Aviv spent")).toBeInTheDocument();
  expect(screen.getByText("Shared categories")).toBeInTheDocument();
  expect(screen.getByText("Housing")).toBeInTheDocument();
  expect(screen.getByText("Groceries")).toBeInTheDocument();
});

test("renders an empty state when fewer than two people", async () => {
  getOverlap.mockResolvedValue({ available: false, a: null, b: null, shared: 0, rows: [] });
  render(<PeopleTab filters={{}} />);
  await waitFor(() => expect(screen.getByText(/Need two people/)).toBeInTheDocument());
});
