const BASE = "/api";

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of entries) sp.set(k, String(v));
  return `?${sp.toString()}`;
}

export async function apiGet<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}${qs(params)}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiSend<T>(method: "POST" | "PATCH" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type Person = { id: number; name: string };
export type Overview = {
  month: string | null;
  months: string[];
  income: number;
  spend: number;
  net: number;
  savings_rate: number | null;
  complete: boolean;
  by_category: Record<string, number>;
};

export const getPeople = () => apiGet<Person[]>("/people");
export const getOverview = (p: { personId?: number; month?: string }) =>
  apiGet<Overview>("/overview", { person_id: p.personId, month: p.month });

export type Transaction = {
  id: number;
  person_id: number;
  date: string;
  description: string;
  amount: number;
  category: string;
  source: string;
  included: number; // 0 | 1
  balance: number | null;
  person: string;
};

export const getTransactions = (p: { personId?: number }) =>
  apiGet<Transaction[]>("/transactions", { person_id: p.personId });

export const updateTransaction = (id: number, body: { category?: string; included?: boolean }) =>
  apiSend<Transaction>("PATCH", `/transactions/${id}`, body);

export type Budget = {
  id: number;
  person_id: number | null;
  category: string;
  amount: number;
  budget: number;
  spent: number;
  expected_to_date: number;
  projected_eom: number;
  pct: number;
  status: "on_track" | "ahead" | "over";
};

export const getBudgets = (p: { personId?: number }) =>
  apiGet<Budget[]>("/budgets", { person_id: p.personId });

export const setBudget = (b: { personId?: number; category: string; amount: number }) =>
  apiSend<{ ok: boolean }>("PUT", "/budgets", { person_id: b.personId, category: b.category, amount: b.amount });

export const deleteBudget = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/budgets/${id}`);

export type RecurringCharge = {
  vendor: string;
  category: string | null;
  cadence: "weekly" | "monthly" | "quarterly" | "yearly";
  kind: "fixed" | "variable";
  typical_amount: number;
  prior_typical: number;
  prior_stable: boolean;
  first_date: string;
  last_date: string;
  last_amount: number;
  next_expected: string;
  count: number;
  monthly_cost: number;
  annual_cost: number;
  confidence: number;
};

export type RecurringAnomaly = {
  vendor: string;
  type: "price_change" | "possibly_canceled" | "new";
  detail: string;
  pct?: number;
  overdue_days?: number;
  age_days?: number;
};

export type Committed = { fixed: number; variable: number; total: number };

export type RecurringData = {
  charges: RecurringCharge[];
  committed: Committed;
  anomalies: RecurringAnomaly[];
};

export const getRecurring = (p: { personId?: number }) =>
  apiGet<RecurringData>("/recurring", { person_id: p.personId });

export type Goal = {
  id: number;
  person_id: number | null;
  name: string;
  target_amount: number;
  saved_amount: number;
  target_date: string | null;
  horizon: string;
  notes: string;
  percent: number;
  monthly_needed: number | null;
};

export const getGoals = (p: { personId?: number }) =>
  apiGet<Goal[]>("/goals", { person_id: p.personId });

export const addGoal = (g: { personId?: number; name: string; targetAmount: number; targetDate?: string; horizon?: string }) =>
  apiSend<{ ok: boolean }>("POST", "/goals", {
    person_id: g.personId, name: g.name, target_amount: g.targetAmount,
    target_date: g.targetDate, horizon: g.horizon ?? "short",
  });

export const updateGoalSaved = (id: number, savedAmount: number) =>
  apiSend<{ ok: boolean }>("PATCH", `/goals/${id}`, { saved_amount: savedAmount });

export const deleteGoal = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/goals/${id}`);

export type Account = {
  id: number;
  person_id: number | null;
  name: string;
  kind: string;
  is_asset: number;
  balance: number;
  updated_at: string;
};

export type NetWorthPoint = { date: string; assets: number; liabilities: number; net: number };

export type NetWorthData = {
  summary: { assets: number; liabilities: number; net: number };
  delta: number | null;
  accounts: Account[];
  trend: NetWorthPoint[];
};

export const getNetWorth = (p: { personId?: number }) =>
  apiGet<NetWorthData>("/networth", { person_id: p.personId });

export const addAccount = (a: { personId?: number; name: string; kind: string; isAsset: boolean; balance: number }) =>
  apiSend<{ ok: boolean; id: number }>("POST", "/networth/accounts", {
    person_id: a.personId, name: a.name, kind: a.kind, is_asset: a.isAsset, balance: a.balance,
  });

export const updateAccountBalance = (id: number, balance: number) =>
  apiSend<{ ok: boolean }>("PATCH", `/networth/accounts/${id}`, { balance });

export const deleteAccount = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/networth/accounts/${id}`);
