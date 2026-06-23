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
export type SpendingAlert = {
  category: string;
  current: number;
  baseline: number;
  delta: number;
  pct: number | null;
  direction: "up" | "down";
  new: boolean;
};
export type OverviewSeriesPoint = {
  month: string;
  income: number;
  spend: number;
  net: number;
  savings_rate: number | null;
  complete: boolean;
};
export type PersonSpend = { person_id: number; name: string; spend: number };
export type Overview = {
  month: string | null;
  months: string[];
  income: number;
  spend: number;
  net: number;
  savings_rate: number | null;
  complete: boolean;
  by_category: Record<string, number>;
  alerts: SpendingAlert[];
  /** Per-month trend (months order) for the cash-flow area + savings-rate bars. */
  series: OverviewSeriesPoint[];
  /** Joint-only per-person spend for the selected month; null in single-persona view. */
  split: PersonSpend[] | null;
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

export type TransferPair = {
  amount: number;
  out_id: number | null;
  in_id: number | null;
  out_date: string;
  in_date: string;
  out_desc: string;
  in_desc: string;
  out_person: number | null;
  in_person: number | null;
  days_apart: number;
  cross_person: boolean;
  both_included: boolean;
};

export const getTransferPairs = (personId?: number) =>
  apiGet<TransferPair[]>("/transactions/transfers", { person_id: personId });

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
export type NetWorthSplit = { person_id: number | null; name: string; net: number; assets: number; liabilities: number };

export type NetWorthData = {
  summary: { assets: number; liabilities: number; net: number };
  delta: number | null;
  accounts: Account[];
  trend: NetWorthPoint[];
  split: NetWorthSplit[] | null;
};

export const getNetWorth = (p: { personId?: number }) =>
  apiGet<NetWorthData>("/networth", { person_id: p.personId });

export type Reconciliation =
  | { reconcilable: false }
  | {
      reconcilable: true; ok: boolean; begin: number; end: number;
      sum_amounts: number; computed_end: number; discrepancy: number;
      n: number; chain_breaks: number;
    };

export const getReconciliation = (personId?: number) =>
  apiGet<Reconciliation>("/networth/reconcile", { person_id: personId });

export const addAccount = (a: { personId?: number; name: string; kind: string; isAsset: boolean; balance: number }) =>
  apiSend<{ ok: boolean; id: number }>("POST", "/networth/accounts", {
    person_id: a.personId, name: a.name, kind: a.kind, is_asset: a.isAsset, balance: a.balance,
  });

export const updateAccountBalance = (id: number, balance: number) =>
  apiSend<{ ok: boolean }>("PATCH", `/networth/accounts/${id}`, { balance });

export const deleteAccount = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/networth/accounts/${id}`);

export type AccountSnapshot = { date: string; balance: number };
export const getAccountHistory = (id: number) =>
  apiGet<{ snapshots: AccountSnapshot[] }>(`/networth/accounts/${id}/history`);

export type Category = { id: number; person_id: number; name: string; keywords: string; parent?: string | null };
export type Vendor = { id: number; person_id: number; name: string; keywords: string };

export const getCategories = (personId: number) =>
  apiGet<Category[]>("/categories", { person_id: personId });
export const upsertCategory = (c: { personId: number; name: string; keywords: string; parent?: string }) =>
  apiSend<{ ok: boolean }>("PUT", "/categories", {
    person_id: c.personId, name: c.name, keywords: c.keywords,
    ...(c.parent !== undefined ? { parent: c.parent } : {}),
  });
export const deleteCategory = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/categories/${id}`);

export const getVendors = (personId: number) =>
  apiGet<Vendor[]>("/vendors", { person_id: personId });
export const upsertVendor = (v: { personId: number; name: string; keywords: string }) =>
  apiSend<{ ok: boolean }>("PUT", "/vendors", { person_id: v.personId, name: v.name, keywords: v.keywords });
export const deleteVendor = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/vendors/${id}`);

export const renamePerson = (id: number, name: string) =>
  apiSend<{ id: number; name: string }>("PATCH", `/people/${id}`, { name });

export type InsightsPreview = { payload: string; has_key: boolean };

export const getInsightsPreview = (personId?: number) =>
  apiGet<InsightsPreview>("/insights/preview", { person_id: personId });
export const generateInsights = (personId?: number) =>
  apiSend<{ text: string }>("POST", "/insights/generate", { person_id: personId });

export type OllamaStatus = { ok: boolean; message: string };
export type ImportRow = {
  date: string; description: string; amount: number; category: string;
  source: string; included: boolean; balance: number | null;
};
export type ImportParseResult = {
  already_imported: boolean; file_hash: string; filename: string;
  source: string; rows: ImportRow[]; warnings: string[];
};

export const getOllamaStatus = () => apiGet<OllamaStatus>("/import/status");

// Multipart upload — let the browser set the Content-Type boundary, so this
// doesn't go through apiSend (which sends JSON).
export async function parseImport(file: File, source: string, personId: number): Promise<ImportParseResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("source", source);
  fd.append("person_id", String(personId));
  const res = await fetch(`${BASE}/import/parse`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`POST /import/parse -> ${res.status}`);
  return res.json() as Promise<ImportParseResult>;
}

export const commitImport = (c: {
  personId: number; filename: string; fileHash: string; source: string; rows: ImportRow[];
}) =>
  apiSend<{ imported: number }>("POST", "/import/commit", {
    person_id: c.personId, filename: c.filename, file_hash: c.fileHash,
    source: c.source, rows: c.rows,
  });

export type FinanceEvent = {
  id: number;
  person_id: number | null;
  name: string;
  kind: string;
  start_date: string | null;
  end_date: string | null;
  rule: string | null;
  txn_count: number;
  total: number;
};

// ---- Analysis (deep-dive: Explore / Compare / People) ----

/** Shared filter-bar state. Sparse: an absent field means "no constraint". */
export type AnalysisFilters = {
  dateFrom?: string;
  dateTo?: string;
  dayType?: "weekday" | "weekend";
  dow?: number[];
  months?: string[];
  categories?: string[];
  eventId?: number;
};

export type FilterOptions = {
  months: string[];
  categories: string[];
  events: { id: number; name: string; kind: string }[];
};

export const getFilterOptions = (personId?: number) =>
  apiGet<FilterOptions>("/analysis/filter-options", { person_id: personId });

/** Build a full analysis query string: persona + filters (lists become repeated
 *  keys, which FastAPI parses into list params) + any extra scalars. */
export function analysisQuery(
  personId: number | undefined,
  filters: AnalysisFilters = {},
  extra: Record<string, string | number | undefined> = {},
): string {
  const sp = new URLSearchParams();
  const scalars: Record<string, string | number | undefined> = {
    person_id: personId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    day_type: filters.dayType,
    event_id: filters.eventId,
    ...extra,
  };
  for (const [k, v] of Object.entries(scalars)) {
    if (v !== undefined && v !== "") sp.set(k, String(v));
  }
  for (const m of filters.months ?? []) sp.append("months", m);
  for (const c of filters.categories ?? []) sp.append("categories", c);
  for (const d of filters.dow ?? []) sp.append("dow", String(d));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export type CategoryTrend = {
  months: string[];
  series: { name: string; values: number[]; total: number }[];
};

export const getCategoryTrend = (p: { personId?: number; rollup?: boolean; filters?: AnalysisFilters }) =>
  apiGet<CategoryTrend>(`/analysis/category-trend${analysisQuery(p.personId, p.filters, { rollup: p.rollup ? "true" : undefined })}`);

export type DrillItem = { name: string; value: number };
export type DrillRow = { date: string; description: string; amount: number; category: string };
export type DrillResult = { level: "category" | "vendor" | "rows"; items: DrillItem[]; rows: DrillRow[] };

export const getDrill = (p: {
  personId?: number;
  level: "category" | "vendor" | "rows";
  cat?: string;
  vendor?: string;
  filters?: AnalysisFilters;
}) =>
  apiGet<DrillResult>(
    `/analysis/drill${analysisQuery(p.personId, p.filters, { level: p.level, cat: p.cat, vendor: p.vendor })}`,
  );

export type ComparePreset = "weekdays_weekends" | "month_vs_month";
export type CompareMetric = "spend" | "per_day";
export type CompareBucket = { label: string; total: number; per_day: number; n_days: number };
export type CompareResult = {
  preset: ComparePreset;
  metric: CompareMetric;
  buckets: CompareBucket[];
  labels: { a: string; b: string };
  categories: { name: string; a: number; b: number }[];
};

export const getCompare = (p: {
  personId?: number;
  preset: ComparePreset;
  metric: CompareMetric;
  filters?: AnalysisFilters;
}) =>
  apiGet<CompareResult>(
    `/analysis/compare${analysisQuery(p.personId, p.filters, { preset: p.preset, metric: p.metric })}`,
  );

export type OverlapPerson = { id: number; name: string; spend: number; categories: number };
export type OverlapRow = { category: string; a: number; b: number; diff: number; shared: boolean };
export type OverlapResult = {
  available: boolean;
  a: OverlapPerson | null;
  b: OverlapPerson | null;
  shared: number;
  rows: OverlapRow[];
};

export const getOverlap = (p: { filters?: AnalysisFilters } = {}) =>
  apiGet<OverlapResult>(`/analysis/overlap${analysisQuery(undefined, p.filters)}`);

export const getEvents = (personId?: number) =>
  apiGet<FinanceEvent[]>("/events", { person_id: personId });
export const createEvent = (e: { personId?: number; name: string; kind: string }) =>
  apiSend<{ id: number }>("POST", "/events", { person_id: e.personId, name: e.name, kind: e.kind });
export const deleteEvent = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/events/${id}`);
export const getEventTransactions = (id: number) =>
  apiGet<number[]>(`/events/${id}/transactions`);
export const setEventTags = (id: number, transactionIds: number[]) =>
  apiSend<{ ok: boolean }>("PUT", `/events/${id}/transactions`, { transaction_ids: transactionIds });
