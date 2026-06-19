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
