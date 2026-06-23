import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { StackedBars } from "./stacked-bars";

test("renders a row label and value", () => {
  render(<StackedBars rows={[{ label: "Income", value: 5000, pct: 100, color: "var(--pos)" }]} />);
  expect(screen.getByText("Income")).toBeInTheDocument();
  expect(screen.getByText("$5,000.00")).toBeInTheDocument();
});

test("splits a row into committed vs discretionary segments with a legend", () => {
  const { container } = render(
    <StackedBars
      rows={[{
        label: "Spending", value: 315, pct: 60, color: "var(--neg)",
        segments: [
          { label: "Committed", value: 15, color: "var(--neg)" },
          { label: "Discretionary", value: 300, color: "#ccc" },
        ],
      }]}
    />,
  );
  expect(screen.getByText("Committed")).toBeInTheDocument();
  expect(screen.getByText("Discretionary")).toBeInTheDocument();
  // Two segment fills whose widths reflect their share of the row total.
  const segs = Array.from(container.querySelectorAll("[data-segment]")) as HTMLElement[];
  expect(segs).toHaveLength(2);
  expect(segs[0].style.width).not.toBe(segs[1].style.width);
});
