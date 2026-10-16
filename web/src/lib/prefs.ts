// Per-device UI assumptions persisted in localStorage (no server schema). Shared
// so Settings (writer) and NetWorth (reader) agree on the key.

const RETURN_KEY = "homefinance.assumed_annual_return";
const DEFAULT_RETURN = 0.07; // 7% nominal — a stated assumption, editable in Settings.

/** Assumed annual return for net-worth projections, as a fraction (0.07 = 7%). */
export function getAssumedReturn(): number {
  try {
    const v = Number(localStorage.getItem(RETURN_KEY));
    return Number.isFinite(v) && v > 0 ? v : DEFAULT_RETURN;
  } catch {
    return DEFAULT_RETURN;
  }
}

export function setAssumedReturn(rate: number): void {
  try {
    localStorage.setItem(RETURN_KEY, String(rate));
  } catch {
    /* ignore (private mode / disabled storage) */
  }
}
