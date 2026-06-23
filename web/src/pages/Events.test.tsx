import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const getEvents = vi.fn();
const createEvent = vi.fn();
const deleteEvent = vi.fn();
const getTransactions = vi.fn();
const getEventTransactions = vi.fn();
const setEventTags = vi.fn();

vi.mock("@/lib/currency", () => ({
  useCurrency: () => ({ currency: "USD", setCurrency: () => {}, symbol: "$", format: (n: number) => `$${n}` }),
}));
vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getEvents: (...a: unknown[]) => getEvents(...a),
  createEvent: (...a: unknown[]) => createEvent(...a),
  deleteEvent: (...a: unknown[]) => deleteEvent(...a),
  getTransactions: (...a: unknown[]) => getTransactions(...a),
  getEventTransactions: (...a: unknown[]) => getEventTransactions(...a),
  setEventTags: (...a: unknown[]) => setEventTags(...a),
}));

import Events from "./Events";

const EVENTS = [{ id: 7, person_id: 1, name: "Hawaii", kind: "trip", start_date: null, end_date: null, rule: null, txn_count: 2, total: -1000 }];
const TXNS = [
  { id: 1, person_id: 1, date: "2026-05-01", description: "Flight", amount: -400, category: "Travel", source: "card", included: 1, balance: null, person: "Ada" },
  { id: 2, person_id: 1, date: "2026-05-02", description: "Hotel", amount: -600, category: "Travel", source: "card", included: 1, balance: null, person: "Ada" },
  { id: 3, person_id: 1, date: "2026-05-03", description: "Groceries", amount: -50, category: "Food", source: "card", included: 1, balance: null, person: "Ada" },
];

beforeEach(() => {
  getEvents.mockResolvedValue(EVENTS);
  getTransactions.mockResolvedValue(TXNS);
  getEventTransactions.mockResolvedValue([1, 2]);
  createEvent.mockResolvedValue({ id: 8 });
  deleteEvent.mockResolvedValue({ ok: true });
  setEventTags.mockResolvedValue({ ok: true });
});
afterEach(() => vi.clearAllMocks());

test("lists events with their tagged totals", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  expect(screen.getByText(/2 transactions/i)).toBeInTheDocument();
});

test("creating a manual event calls createEvent", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText(/event name/i), "Wedding");
  await userEvent.click(screen.getByRole("button", { name: /add event/i }));
  expect(createEvent).toHaveBeenCalledWith({ personId: 1, name: "Wedding", kind: "tagged" });
});

test("creating a date-window event sends start/end dates", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText(/event name/i), "Trip");
  await userEvent.selectOptions(screen.getByLabelText("Membership"), "window");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-04-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-04-30");
  await userEvent.click(screen.getByRole("button", { name: /add event/i }));
  expect(createEvent).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Trip", kind: "window", startDate: "2026-04-01", endDate: "2026-04-30" }),
  );
});

test("creating a recurring event sends a dow rule", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText(/event name/i), "Weekends");
  await userEvent.selectOptions(screen.getByLabelText("Membership"), "recurring");
  await userEvent.click(screen.getByLabelText("Day Sa"));
  await userEvent.click(screen.getByLabelText("Day Su"));
  await userEvent.click(screen.getByRole("button", { name: /add event/i }));
  expect(createEvent).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Weekends", kind: "recurring", rule: { dow: [5, 6] } }),
  );
});

test("tagging transactions to an event calls setEventTags", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: /tag transactions for Hawaii/i }));
  await waitFor(() => expect(screen.getByLabelText(/Tag Groceries/i)).toBeInTheDocument());
  await userEvent.click(screen.getByLabelText(/Tag Groceries/i));
  await userEvent.click(screen.getByRole("button", { name: /save members/i }));
  expect(setEventTags).toHaveBeenCalledWith(7, expect.arrayContaining([1, 2, 3]));
});

test("deleting an event calls deleteEvent", async () => {
  render(<Events />);
  await waitFor(() => expect(screen.getByText("Hawaii")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: /delete Hawaii/i }));
  expect(deleteEvent).toHaveBeenCalledWith(7);
});
