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

// ─── Partial (in-progress month) marker ───────────────────────────────────────

test("partial bar renders a hatched fill and is flagged data-partial", () => {
  const { container } = render(
    <BarChart
      series={[{ label: "May", value: 80 }, { label: "Jun", value: 40 }]}
      partial={[false, true]}
    />,
  );

  const partialBar = container.querySelector("[data-partial='true']") as HTMLElement;
  expect(partialBar).toBeTruthy();
  // Hatched = a repeating-linear-gradient overlay (the Frosted Ledger "provisional" cue)
  expect(partialBar.style.backgroundImage).toContain("repeating-linear-gradient");

  // The complete bar carries no partial flag.
  const allBars = Array.from(container.querySelectorAll("[data-sign]"));
  const nonPartial = allBars.filter((b) => b.getAttribute("data-partial") !== "true");
  expect(nonPartial).toHaveLength(1);
});

test("partial bar surfaces a (so far) affordance", () => {
  const { getByText } = render(
    <BarChart
      series={[{ label: "May", value: 80 }, { label: "Jun", value: 40 }]}
      partial={[false, true]}
    />,
  );
  expect(getByText(/so far/i)).toBeTruthy();
});

test("no partial markers when partial prop omitted (backward compatible)", () => {
  const { container, queryByText } = render(
    <BarChart series={[{ label: "May", value: 80 }, { label: "Jun", value: 40 }]} />,
  );
  expect(container.querySelector("[data-partial='true']")).toBeNull();
  expect(queryByText(/so far/i)).toBeNull();
});
