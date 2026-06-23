import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { BarChart } from "./bar-chart";

// ─── Signed domain tests ──────────────────────────────────────────────────────

test("negative bar renders below baseline with negative color", () => {
  const { container } = render(
    <BarChart series={[{ label: "Jan", value: -30 }, { label: "Feb", value: 30 }]} />,
  );

  const bars = container.querySelectorAll("[data-sign]");
  expect(bars).toHaveLength(2);

  const negBar = container.querySelector("[data-sign='neg']");
  const posBar = container.querySelector("[data-sign='pos']");

  expect(negBar).toBeTruthy();
  expect(posBar).toBeTruthy();

  // Negative bar should use the negative color token
  expect((negBar as HTMLElement).style.background).toContain("var(--neg)");

  // Positive bar should NOT use the negative color token
  expect((posBar as HTMLElement).style.background).not.toContain("var(--neg)");
});

test("zero baseline element is present", () => {
  const { container } = render(
    <BarChart series={[{ label: "Jan", value: -30 }, { label: "Feb", value: 30 }]} />,
  );

  const zeroline = container.querySelector("[data-zero-line]");
  expect(zeroline).toBeTruthy();
});

test("+30 and -30 render with equal bar magnitude", () => {
  const { container } = render(
    <BarChart series={[{ label: "Jan", value: -30 }, { label: "Feb", value: 30 }]} />,
  );

  const negBar = container.querySelector("[data-sign='neg']") as HTMLElement;
  const posBar = container.querySelector("[data-sign='pos']") as HTMLElement;

  // Both should have the same height percentage (equal magnitude)
  expect(negBar.style.height).toBe(posBar.style.height);
});

// ─── Regression: all-positive series ─────────────────────────────────────────

test("all-positive series renders all bars above baseline (pos sign)", () => {
  const { container } = render(
    <BarChart
      series={[
        { label: "Jan", value: 40 },
        { label: "Feb", value: 80 },
        { label: "Mar", value: 20 },
      ]}
    />,
  );

  const bars = container.querySelectorAll("[data-sign]");
  expect(bars).toHaveLength(3);

  bars.forEach((bar) => {
    expect(bar.getAttribute("data-sign")).toBe("pos");
  });

  // No negative bars
  expect(container.querySelector("[data-sign='neg']")).toBeNull();
});

test("zero-value bar renders as pos (not neg)", () => {
  const { container } = render(
    <BarChart series={[{ label: "Jan", value: 0 }]} />,
  );
  const bar = container.querySelector("[data-sign]");
  expect(bar?.getAttribute("data-sign")).toBe("pos");
});
