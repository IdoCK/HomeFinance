import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { BarChartR } from "./r-bar-chart";

const labels = ["Groceries", "Transport"];
const series = [
  { name: "Weekdays", values: [120, 60], total: 180 },
  { name: "Weekends", values: [200, 30], total: 230 },
];

test("empty state with no labels", () => {
  render(<BarChartR series={series} labels={[]} />);
  expect(screen.getByText(/No data in range/)).toBeInTheDocument();
});

test("legend lists both buckets with bold totals", () => {
  render(<BarChartR series={series} labels={labels} />);
  expect(screen.getByText("$180.00")).toBeInTheDocument();
  expect(screen.getByText("$230.00")).toBeInTheDocument();
});

test("screen-reader table carries every category × bucket figure", () => {
  render(<BarChartR series={series} labels={labels} ariaLabel="Weekdays versus Weekends by category" />);
  const table = screen.getByRole("table", { name: /Weekdays versus Weekends/i });
  expect(within(table).getByText("Groceries")).toBeInTheDocument();
  expect(within(table).getByText("$200.00")).toBeInTheDocument();
});
