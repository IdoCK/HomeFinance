import { useEffect, useRef, useState } from "react";
import { getDrill, getVendors, groupVendor, ungroupVendor, type AnalysisFilters, type DrillResult, type Vendor } from "@/lib/api";
import { Money, formatMoney } from "@/components/money";
import { useCurrency } from "@/lib/currency";
import { Loading } from "@/components/loading";

/** Category → vendor → rows drill-down (the old Explore drill). Holds a small
 *  path: [] = categories, [cat] = vendors in that category, [cat, vendor] = the
 *  underlying rows. Clicking a ranked bar drills in; the breadcrumb climbs back. */
export function DrillDown({ personId, filters }: { personId?: number; filters: AnalysisFilters }) {
  const { currency } = useCurrency();
  const [path, setPath] = useState<string[]>([]);
  const [data, setData] = useState<DrillResult | null>(null);
  // Bumped after a group/ungroup edit to re-fetch the (now re-grouped) drill.
  const [reloadKey, setReloadKey] = useState(0);
  const dragVendor = useRef<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  // The persona's vendor rules — tells us which drill items are groups and what
  // merchants they contain, so a group can be expanded and its members removed.
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Reset to the top whenever the persona or filters change (the old context is gone).
  // Keep the same reference when already at the top so we don't trigger a spurious
  // re-render (and a double drill fetch) on mount.
  useEffect(() => { setPath((p) => (p.length === 0 ? p : [])); }, [personId, filters]);

  useEffect(() => {
    let alive = true;
    setData(null);
    const level = path.length === 0 ? "category" : path.length === 1 ? "vendor" : "rows";
    getDrill({ personId, level, cat: path[0], vendor: path[1], filters, display: currency })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData({ level, items: [], rows: [] }));
    return () => { alive = false; };
  }, [personId, filters, path, currency, reloadKey]);

  // Keep the vendor rules in sync (re-fetch after a group/ungroup edit so the
  // expanded member chips reflect the change). Per-person only.
  useEffect(() => {
    if (personId == null) { setVendors([]); return; }
    let alive = true;
    getVendors(personId).then((v) => alive && setVendors(v)).catch(() => alive && setVendors([]));
    return () => { alive = false; };
  }, [personId, reloadKey]);

  // Vendor rules are per-person, so grouping is only available in a person view
  // (not Joint). At the vendor level you can drag one merchant onto another to
  // fold it into that group, or expand a group to remove a member.
  const canGroup = personId != null && data?.level === "vendor";
  // name -> the merchant keywords that make up that group (≥2 = a real group).
  const memberMap = new Map(
    vendors.map((v) => [v.name, (v.keywords || "").split(",").map((k) => k.trim()).filter(Boolean)]),
  );

  const onDropVendor = async (target: string) => {
    const src = dragVendor.current;
    dragVendor.current = null;
    setDropTarget(null);
    if (personId == null || !src || src === target) return;
    try {
      await groupVendor({ personId, target, keyword: src });
      setReloadKey((k) => k + 1);
    } catch { /* ignore — leave the view unchanged */ }
  };

  const removeMember = async (target: string, keyword: string) => {
    if (personId == null) return;
    try {
      await ungroupVendor({ personId, target, keyword });
      setReloadKey((k) => k + 1);
    } catch { /* ignore — leave the view unchanged */ }
  };

  const toggleExpand = (name: string) =>
    setExpanded((s) => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n; });

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
          {canGroup && data.items.length > 1 && (
            <p style={{ margin: 0, fontSize: 11.5, color: "var(--fl-muted)" }}>
              Drag a merchant onto another to group them; open a group (▸) to remove a member.
            </p>
          )}
          {data.items.map((it) => {
            const isDropTarget = dropTarget === it.name;
            const members = memberMap.get(it.name) ?? [];
            const isGroup = canGroup && members.length >= 2;
            const isOpen = expanded.has(it.name);
            return (
              <div
                key={it.name}
                draggable={canGroup || undefined}
                onDragStart={canGroup ? (e) => { dragVendor.current = it.name; e.dataTransfer.effectAllowed = "move"; } : undefined}
                onDragOver={canGroup ? (e) => {
                  if (dragVendor.current && dragVendor.current !== it.name) {
                    e.preventDefault();
                    if (dropTarget !== it.name) setDropTarget(it.name);
                  }
                } : undefined}
                onDragLeave={canGroup ? () => setDropTarget((t) => (t === it.name ? null : t)) : undefined}
                onDrop={canGroup ? (e) => { e.preventDefault(); onDropVendor(it.name); } : undefined}
                style={{
                  display: "grid", gap: 6, padding: "4px 6px",
                  background: isDropTarget ? "color-mix(in srgb, var(--persona-solid) 12%, transparent)" : "none",
                  border: isDropTarget ? "1px dashed var(--persona-solid)" : "1px solid transparent",
                  borderRadius: 8, cursor: canGroup ? "grab" : "default",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    onClick={() => setPath([...path, it.name])}
                    aria-label={`Drill into ${it.name}`}
                    style={{ flex: 1, minWidth: 0, display: "grid", gap: 5, textAlign: "left", background: "none", border: "none", padding: 0, cursor: "pointer" }}
                  >
                    <span style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: 13 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {it.name}
                        <span aria-hidden style={{ color: "var(--fl-muted)", fontSize: 11 }}>›</span>
                      </span>
                      <b style={{ fontWeight: 800, letterSpacing: "-0.02em", flex: "none" }}>{formatMoney(it.value)}</b>
                    </span>
                    <span style={{ height: 6, borderRadius: 99, background: "var(--fl-frame)", overflow: "hidden" }}>
                      <span style={{ display: "block", height: "100%", borderRadius: 99, width: `${(it.value / max) * 100}%`, background: "var(--persona-solid)", transition: "width 240ms ease" }} />
                    </span>
                  </button>
                  {isGroup && (
                    <button
                      onClick={() => toggleExpand(it.name)}
                      aria-expanded={isOpen}
                      aria-label={`${isOpen ? "Hide" : "Show"} merchants grouped under ${it.name}`}
                      style={{ flex: "none", background: "none", border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 9px", fontSize: 11, fontWeight: 600, color: "var(--fl-muted)", cursor: "pointer" }}
                    >
                      {isOpen ? "▾" : "▸"} {members.length}
                    </button>
                  )}
                </div>
                {isGroup && isOpen && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, paddingLeft: 2 }}>
                    {members.map((kw) => (
                      <span key={kw} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, padding: "2px 6px 2px 10px", borderRadius: 999, border: "1px solid var(--fl-line)", color: "var(--fl-ink)" }}>
                        {kw}
                        <button
                          onClick={() => removeMember(it.name, kw)}
                          aria-label={`Remove ${kw} from ${it.name}`}
                          title={`Remove “${kw}” from ${it.name}`}
                          style={{ background: "none", border: "none", color: "var(--fl-muted)", cursor: "pointer", padding: 0, lineHeight: 1, fontSize: 13 }}
                        >
                          ✕
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Empty() {
  return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>Nothing to show in range.</div>;
}
