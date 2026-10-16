import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { LineChart } from "./r-line-chart";

// Recharts' ResponsiveContainer measures 0×0 in jsdom, so the SVG itself doesn't
// render here. We test the behaviour that DOES render and that encodes the house
// conventions: the screen-reader data table (formatMoney values, month labels),
// the bold-total legend, the empty state, and the partial-month affordance.

const series = [
  { name: "Housing", values: [2000, 2000], total: 4000 },
  { name: "Groceries", values: [300, 250], total: 550 },
];
const labels = ["2026-04", "2026-05"];

test("shows an empty state with no series", () => {
  render(<LineChart series={[]} labels={[]} />);
  expect(screen.getByText(/No spending in range/)).toBeInTheDocument();
});

test("legend shows each series with its bold total via formatMoney", () => {
  render(<LineChart series={series} labels={labels} />);
  expect(screen.getByText("$4,000.00")).toBeInTheDocument();
  expect(screen.getByText("$550.00")).toBeInTheDocument();
});

test("exposes a screen-reader data table with month labels and per-cell figures", () => {
  render(<LineChart series={series} labels={labels} ariaLabel="Spending by category over time" />);
  const table = screen.getByRole("table", { name: "Spending by category over time" });
  // Month rows are human-formatted, not raw "2026-04".
  expect(within(table).getByText("Apr 2026")).toBeInTheDocument();
  expect(within(table).getByText("May 2026")).toBeInTheDocument();
  // Each settled cell is formatted through formatMoney.
  expect(within(table).getAllByText("$2,000.00").length).toBe(2);
});

test("surfaces a 'still in progress' affordance for partial months", () => {
  render(<LineChart series={series} labels={labels} partial={[false, true]} />);
  expect(screen.getByText(/still in progress/i)).toBeInTheDocument();
  expect(screen.getByText(/May 2026 onward/i)).toBeInTheDocument();
});

test("no partial affordance when all months are settled", () => {
  render(<LineChart series={series} labels={labels} />);
  expect(screen.queryByText(/still in progress/i)).not.toBeInTheDocument();
});
