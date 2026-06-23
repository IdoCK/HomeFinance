import { useEffect, useState } from "react";
import { getDrill, type AnalysisFilters, type DrillResult } from "@/lib/api";
import { Money, formatMoney } from "@/components/money";
import { Loading } from "@/components/loading";

/** Category → vendor → rows drill-down (the old Explore drill). Holds a small
 *  path: [] = categories, [cat] = vendors in that category, [cat, vendor] = the
 *  underlying rows. Clicking a ranked bar drills in; the breadcrumb climbs back. */
export function DrillDown({ personId, filters }: { personId?: number; filters: AnalysisFilters }) {
  const [path, setPath] = useState<string[]>([]);
  const [data, setData] = useState<DrillResult | null>(null);

  // Reset to the top whenever the persona or filters change (the old context is gone).
  // Keep the same reference when already at the top so we don't trigger a spurious
  // re-render (and a double drill fetch) on mount.
  useEffect(() => { setPath((p) => (p.length === 0 ? p : [])); }, [personId, filters]);

  useEffect(() => {
    let alive = true;
    setData(null);
    const level = path.length === 0 ? "category" : path.length === 1 ? "vendor" : "rows";
    getDrill({ personId, level, cat: path[0], vendor: path[1], filters })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData({ level, items: [], rows: [] }));
    return () => { alive = false; };
  }, [personId, filters, path]);

  const crumbs = ["All categories", ...path];
  const max = Math.max(1, ...(data?.items ?? []).map((i) => i.value));

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <nav aria-label="Drill path" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, flexWrap: "wrap" }}>
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <span key={`${c}-${i}`} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              {i > 0 && <span aria-hidden style={{ color: "var(--fl-muted)" }}>›</span>}
              {last ? (
                <span style={{ fontWeight: 700 }}>{c}</span>
              ) : (
                <button
                  onClick={() => setPath(path.slice(0, i))}
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "var(--persona-solid)", fontWeight: 600 }}
                >
                  {c}
                </button>
              )}
            </span>
          );
        })}
      </nav>

      {data == null ? (
        <Loading rows={2} />
      ) : data.level === "rows" ? (
        <div style={{ display: "grid", gap: 2 }}>
          {data.rows.length === 0 && <Empty />}
          {data.rows.map((r, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 2px", borderBottom: "1px solid var(--fl-line)", fontSize: 13 }}>
              <span style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums", flex: "none", width: 78 }}>{r.date}</span>
              <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.description}</span>
              <Money value={r.amount} colored />
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "grid", gap: 9 }}>
          {data.items.length === 0 && <Empty />}
          {data.items.map((it) => (
            <button
              key={it.name}
              onClick={() => setPath([...path, it.name])}
              aria-label={`Drill into ${it.name}`}
              style={{ display: "grid", gap: 5, textAlign: "left", background: "none", border: "none", padding: "2px 0", cursor: "pointer", width: "100%" }}
            >
              <span style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: 13 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {it.name}
                  <span aria-hidden style={{ color: "var(--fl-muted)", fontSize: 11 }}>›</span>
                </span>
                <b style={{ fontWeight: 800, letterSpacing: "-0.02em" }}>{formatMoney(it.value)}</b>
              </span>
              <span style={{ height: 6, borderRadius: 99, background: "var(--fl-frame)", overflow: "hidden" }}>
                <span style={{ display: "block", height: "100%", borderRadius: 99, width: `${(it.value / max) * 100}%`, background: "var(--persona-solid)", transition: "width 240ms ease" }} />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Empty() {
  return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>Nothing to show in range.</div>;
}
