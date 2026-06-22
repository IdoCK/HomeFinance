import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Loading } from "./loading";

test("renders an accessible loading status", () => {
  render(<Loading />);
  expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading");
});

test("renders the requested number of skeleton rows", () => {
  const { container } = render(<Loading rows={5} />);
  expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(5);
});
