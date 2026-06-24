import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { Sparkline } from "./sparkline";

test("renders an svg trend for >= 2 points", () => {
  const { container } = render(<Sparkline values={[1, 2, 3]} />);
  expect(container.querySelector("svg")).not.toBeNull();
});

test("refuses to draw a trend from a single point", () => {
  const { container } = render(<Sparkline values={[5]} />);
  expect(container.querySelector("svg")).toBeNull();
});

test("refuses to draw from zero points", () => {
  const { container } = render(<Sparkline values={[]} />);
  expect(container.querySelector("svg")).toBeNull();
});

test("shows an empty label when provided and under the 2-point gate", () => {
  const { getByText, container } = render(
    <Sparkline values={[5]} emptyLabel="Need 2+ snapshots" />,
  );
  expect(getByText("Need 2+ snapshots")).toBeTruthy();
  expect(container.querySelector("svg")).toBeNull();
});
