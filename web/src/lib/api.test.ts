import { afterEach, expect, test, vi } from "vitest";
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring, getGoals, addGoal, updateGoalSaved, deleteGoal, getNetWorth, addAccount, updateAccountBalance, deleteAccount, getCategories, upsertCategory, deleteCategory, getVendors, upsertVendor, deleteVendor, renamePerson, getInsightsPreview, generateInsights, getOllamaStatus, parseImport, commitImport, getReconciliation, type ImportRow } from "./api";

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

test("getNetWorth builds /api/networth with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ summary: { assets: 0, liabilities: 0, net: 0 }, delta: null, accounts: [], trend: [] }) });
  vi.stubGlobal("fetch", fetchMock);
  await getNetWorth({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/networth?person_id=1");
});

test("addAccount POSTs derived is_asset", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 1 }) });
  vi.stubGlobal("fetch", fetchMock);
  await addAccount({ personId: 1, name: "Vanguard", kind: "investment", isAsset: true, balance: 25000 });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, name: "Vanguard", kind: "investment", is_asset: true, balance: 25000 });
});

test("updateAccountBalance PATCHes balance", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateAccountBalance(3, 1500);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts/3");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ balance: 1500 });
});

test("deleteAccount DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteAccount(3);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts/3");
  expect(init.method).toBe("DELETE");
});

test("getCategories builds /api/categories with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getCategories(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/categories?person_id=1");
});

test("upsertCategory PUTs person_id + name + keywords", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await upsertCategory({ personId: 1, name: "Travel", keywords: "airbnb,delta" });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/categories");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, name: "Travel", keywords: "airbnb,delta" });
});

test("deleteCategory DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteCategory(10);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/categories/10");
  expect(init.method).toBe("DELETE");
});

test("getVendors builds /api/vendors with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getVendors(2);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/vendors?person_id=2");
});

test("upsertVendor PUTs person_id + name + keywords", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await upsertVendor({ personId: 2, name: "Amazon", keywords: "amazon,amzn" });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/vendors");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 2, name: "Amazon", keywords: "amazon,amzn" });
});

test("deleteVendor DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteVendor(20);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/vendors/20");
  expect(init.method).toBe("DELETE");
});

test("renamePerson PATCHes the people endpoint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1, name: "Adelaide" }) });
  vi.stubGlobal("fetch", fetchMock);
  await renamePerson(1, "Adelaide");
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/people/1");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ name: "Adelaide" });
});

test("getInsightsPreview builds /api/insights/preview with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ payload: "[]", has_key: false }) });
  vi.stubGlobal("fetch", fetchMock);
  await getInsightsPreview(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/insights/preview?person_id=1");
});

test("getInsightsPreview omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ payload: "[]", has_key: false }) });
  vi.stubGlobal("fetch", fetchMock);
  await getInsightsPreview(undefined);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/insights/preview");
});

test("generateInsights POSTs person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ text: "ok" }) });
  vi.stubGlobal("fetch", fetchMock);
  await generateInsights(2);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/insights/generate");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 2 });
});

test("getReconciliation builds /api/networth/reconcile with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ reconcilable: false }) });
  vi.stubGlobal("fetch", fetchMock);
  await getReconciliation(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/networth/reconcile?person_id=1");
});

test("getOllamaStatus builds /api/import/status", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, message: "ready" }) });
  vi.stubGlobal("fetch", fetchMock);
  await getOllamaStatus();
  expect(fetchMock.mock.calls[0][0]).toBe("/api/import/status");
});

test("parseImport posts multipart form data", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ already_imported: false, rows: [] }) });
  vi.stubGlobal("fetch", fetchMock);
  const file = new File(["date,amt"], "june.csv", { type: "text/csv" });
  await parseImport(file, "bank", 1);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/import/parse");
  expect(init.method).toBe("POST");
  expect(init.body).toBeInstanceOf(FormData);
  const fd = init.body as FormData;
  expect(fd.get("source")).toBe("bank");
  expect(fd.get("person_id")).toBe("1");
  expect((fd.get("file") as File).name).toBe("june.csv");
});

test("commitImport posts the rows as JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ imported: 1 }) });
  vi.stubGlobal("fetch", fetchMock);
  const rows: ImportRow[] = [{ date: "2026-06-01", description: "WF", amount: -5, category: "Groceries", source: "bank", included: true, balance: null }];
  await commitImport({ personId: 1, filename: "june.csv", fileHash: "abc", source: "bank", rows });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/import/commit");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, filename: "june.csv", file_hash: "abc", source: "bank", rows });
});
