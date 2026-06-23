import { render, screen, fireEvent } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { FilterBar } from "./filter-bar";
import type { AnalysisFilters, FilterOptions } from "@/lib/api";

const options: FilterOptions = {
  months: ["2026-04", "2026-05"],
  categories: ["Housing", "Groceries"],
  events: [{ id: 1, name: "Trip", kind: "window" }],
};

function setup(value: AnalysisFilters = {}) {
  const onChange = vi.fn();
  render(<FilterBar options={options} value={value} onChange={onChange} />);
  return onChange;
}

test("toggling a day-of-week pill emits the engine dow index (Mon=0)", () => {
  const onChange = setup();
  fireEvent.click(screen.getByLabelText("Day Su")); // Sunday → 6
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dow: [6] }));
});

test("dow toggles off when reselected", () => {
  const onChange = setup({ dow: [6] });
  fireEvent.click(screen.getByLabelText("Day Su"));
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dow: undefined }));
});

test("a single month is selectable and ANDs into the filter set", () => {
  const onChange = setup({ categories: ["Groceries"] });
  fireEvent.click(screen.getByText("2026-05"));
  expect(onChange).toHaveBeenCalledWith({ categories: ["Groceries"], months: ["2026-05"] });
});
