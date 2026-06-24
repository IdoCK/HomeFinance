// Per-device persistence for Studio's saved charts. localStorage only — true to
// the app's "🔒 Local only" promise; no spec or figure ever leaves the device.
import type { ChartSpec } from "@/lib/chart-spec";

const KEY = "homefinance.studio_charts";

export function loadCharts(): ChartSpec[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChartSpec[]) : [];
  } catch {
    return [];
  }
}

function persist(charts: ChartSpec[]): ChartSpec[] {
  try {
    localStorage.setItem(KEY, JSON.stringify(charts));
  } catch {
    /* ignore (private mode / disabled storage) */
  }
  return charts;
}

export function addChart(spec: ChartSpec): ChartSpec[] {
  return persist([...loadCharts(), spec]);
}

export function removeChart(id: string): ChartSpec[] {
  return persist(loadCharts().filter((c) => c.id !== id));
}

/** Move a saved chart one slot earlier/later on the board. */
export function moveChart(id: string, dir: -1 | 1): ChartSpec[] {
  const charts = loadCharts();
  const i = charts.findIndex((c) => c.id === id);
  const j = i + dir;
  if (i === -1 || j < 0 || j >= charts.length) return charts;
  [charts[i], charts[j]] = [charts[j], charts[i]];
  return persist(charts);
}

export function newId(): string {
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}
