import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DotMatrix } from "./dot-matrix";

const segs = [
  { value: 80, color: "#A855F7", label: "Ido" },
  { value: 120, color: "#EC4899", label: "Aviv" },
];

test("renders a text label per segment in the legend", () => {
  render(<DotMatrix segments={segs} />);
  expect(screen.getByText("Ido")).toBeInTheDocument();
  expect(screen.getByText("Aviv")).toBeInTheDocument();
});

test("segments carry a non-color shape cue (colorblind-safe)", () => {
  const { container } = render(<DotMatrix segments={segs} />);
  const swatches = Array.from(container.querySelectorAll("[data-swatch]")) as HTMLElement[];
  expect(swatches.length).toBeGreaterThanOrEqual(2);
  // The first two segments must differ in SHAPE, not only color.
  expect(swatches[0].style.borderRadius).not.toBe(swatches[1].style.borderRadius);
});

test("the dot grid exposes an accessible label", () => {
  const { container } = render(<DotMatrix segments={segs} />);
  const grid = container.querySelector("[role='img']");
  expect(grid).toBeTruthy();
  expect(grid?.getAttribute("aria-label")).toMatch(/Ido|Aviv/);
});

test("bar variant also renders the legend labels", () => {
  render(<DotMatrix segments={segs} variant="bar" />);
  expect(screen.getByText("Ido")).toBeInTheDocument();
  expect(screen.getByText("Aviv")).toBeInTheDocument();
});
