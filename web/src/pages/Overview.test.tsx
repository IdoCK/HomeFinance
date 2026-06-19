import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({
  getOverview: vi.fn().mockResolvedValue({
    month: "2026-05", months: ["2026-04", "2026-05"],
    income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true,
    by_category: { Housing: 2000, Groceries: 300, "Eating out": 100 },
  }),
}));

import Overview from "./Overview";

afterEach(() => vi.restoreAllMocks());

test("renders headline numbers and category breakdown", async () => {
  render(<Overview />);
  await waitFor(() => expect(screen.getByTestId("net")).toHaveTextContent("$2,600.00"));
  expect(screen.getByTestId("income")).toHaveTextContent("$5,000.00");
  expect(screen.getByTestId("spend")).toHaveTextContent("$2,400.00");
  expect(screen.getByText("52%")).toBeInTheDocument();
  expect(screen.getByText("Housing")).toBeInTheDocument();
});
