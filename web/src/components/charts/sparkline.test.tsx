import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { Sparkline } from "./sparkline";

test("renders a chart for >= 2 points", () => {
  // Recharts renders nothing inside a zero-size jsdom container, but it always
  // mounts the ResponsiveContainer wrapper — its presence proves the ≥2-point
  // gate passed and a trend chart (not the null gate) was rendered.
  const { container } = render(<Sparkline values={[1, 2, 3]} />);
  expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
});

test("refuses to draw a trend from a single point", () => {
  const { container } = render(<Sparkline values={[5]} />);
  expect(container.querySelector(".recharts-responsive-container")).toBeNull();
});

test("refuses to draw from zero points", () => {
  const { container } = render(<Sparkline values={[]} />);
  expect(container.querySelector(".recharts-responsive-container")).toBeNull();
});

test("shows an empty label when provided and under the 2-point gate", () => {
  const { getByText, container } = render(
    <Sparkline values={[5]} emptyLabel="Need 2+ snapshots" />,
  );
  expect(getByText("Need 2+ snapshots")).toBeTruthy();
  expect(container.querySelector(".recharts-responsive-container")).toBeNull();
});
