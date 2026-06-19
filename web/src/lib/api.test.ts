import { afterEach, expect, test, vi } from "vitest";
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring, getGoals, addGoal, updateGoalSaved, deleteGoal } from "./api";

afterEach(() => vi.restoreAllMocks());

test("getOverview builds /api/overview with person_id+month and returns JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ month: "2026-05", months: ["2026-05"], income: 10, spend: 4, net: 6, savings_rate: 0.6, complete: true, by_category: { Rent: 4 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const d = await getOverview({ personId: 1, month: "2026-05" });

  const url = fetchMock.mock.calls[0][0] as string;
  expect(url).toBe("/api/overview?person_id=1&month=2026-05");
  expect(d.net).toBe(6);
});

test("getOverview omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);
  await getOverview({});
  expect(fetchMock.mock.calls[0][0]).toBe("/api/overview");
});

test("getTransactions builds /api/transactions with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getTransactions({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/transactions?person_id=1");
});

test("getTransactions omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getTransactions({});
  expect(fetchMock.mock.calls[0][0]).toBe("/api/transactions");
});

test("updateTransaction PATCHes category + included", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 5 }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateTransaction(5, { category: "Rent", included: false });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/transactions/5");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ category: "Rent", included: false });
});

test("getBudgets builds /api/budgets with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getBudgets({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/budgets?person_id=1");
});

test("setBudget PUTs person_id + category + amount", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await setBudget({ personId: 1, category: "Rent", amount: 2000 });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/budgets");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, category: "Rent", amount: 2000 });
});

test("deleteBudget DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteBudget(7);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/budgets/7");
  expect(init.method).toBe("DELETE");
});

test("getRecurring builds /api/recurring with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ charges: [], committed: { fixed: 0, variable: 0, total: 0 }, anomalies: [] }) });
  vi.stubGlobal("fetch", fetchMock);
  await getRecurring({ personId: 2 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/recurring?person_id=2");
});

test("getGoals builds /api/goals with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getGoals({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/goals?person_id=1");
});

test("addGoal POSTs name + target + horizon", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await addGoal({ personId: 1, name: "Car", targetAmount: 20000 });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toMatchObject({ person_id: 1, name: "Car", target_amount: 20000, horizon: "short" });
});

test("updateGoalSaved PATCHes saved_amount", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateGoalSaved(7, 1500);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals/7");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ saved_amount: 1500 });
});

test("deleteGoal DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteGoal(7);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals/7");
  expect(init.method).toBe("DELETE");
});
