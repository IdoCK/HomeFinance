import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const getInsightsPreview = vi.fn();
const generateInsights = vi.fn();

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getInsightsPreview: (...a: unknown[]) => getInsightsPreview(...a),
  generateInsights: (...a: unknown[]) => generateInsights(...a),
}));

import Insights from "./Insights";

afterEach(() => {
  getInsightsPreview.mockReset();
  generateInsights.mockReset();
});

test("shows the hero and the exact payload that would be sent", async () => {
  getInsightsPreview.mockResolvedValue({ payload: '{"who":"Person A"}', has_key: true });
  render(<Insights />);
  await waitFor(() => expect(screen.getByText(/what the numbers say/i)).toBeInTheDocument());
  expect(screen.getByText(/"who":"Person A"/)).toBeInTheDocument();
});

test("Generate calls generateInsights and renders the returned text", async () => {
  getInsightsPreview.mockResolvedValue({ payload: "{}", has_key: true });
  generateInsights.mockResolvedValue({ text: "You saved 24% this month." });
  render(<Insights />);
  await waitFor(() => expect(screen.getByRole("button", { name: /generate insights/i })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: /generate insights/i }));
  expect(generateInsights).toHaveBeenCalledWith(1);
  await waitFor(() => expect(screen.getByText("You saved 24% this month.")).toBeInTheDocument());
});

test("without an API key the button is disabled and explains why", async () => {
  getInsightsPreview.mockResolvedValue({ payload: "{}", has_key: false });
  render(<Insights />);
  await waitFor(() => expect(screen.getByRole("button", { name: /generate insights/i })).toBeDisabled());
  expect(screen.getByText(/set ANTHROPIC_API_KEY to enable/i)).toBeInTheDocument();
});
