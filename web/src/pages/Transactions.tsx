import { useEffect, useMemo, useRef, useState } from "react";
import { pillStyle as pill } from "@/lib/ui";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnOrderState,
  type ColumnSizingState,
  type SortingState,
} from "@tanstack/react-table";
import { getTransactions, updateTransaction, getTransferPairs, type Transaction, type TransferPair } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { Money, formatMoney } from "@/components/money";

type IncludeFilter = "all" | "in" | "out";
type Person = { id: number; name: string };

// ponytail: persona colors are keyed by people[0]/[1] (Ido/Aviv). Ceiling: only the
// first two people get a signature color; a third+ person falls back to the hairline.
const personaColor = (personId: number, people: Person[]) =>
  personId === people[0]?.id ? "var(--persona-you)"
  : personId === people[1]?.id ? "var(--persona-spouse)"
  : "var(--fl-line)";

// Default left-to-right order; "person" only exists in Joint view. Reorder + resize
// are user-adjustable (drag headers / drag borders) and persisted per device.
const ORDER_KEY = "homefinance.txn.column_order";
const SIZE_KEY = "homefinance.txn.column_sizing";
const defaultOrder = (joint: boolean): string[] =>
  joint
    ? ["date", "description", "person", "category", "amount", "original", "included"]
    : ["date", "description", "category", "amount", "original", "included"];

function loadJSON<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
function saveJSON(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore (private mode / disabled storage) */
  }
}

// Keep a saved order valid as columns appear/disappear (the Joint "person" column):
// drop unknown ids, then splice any missing ones back at their default position.
function reconcileOrder(defaults: string[], saved: string[]): string[] {
  const result = saved.filter((id) => defaults.includes(id));
  for (const id of defaults) {
    if (result.includes(id)) continue;
    const di = defaults.indexOf(id);
    let at = result.length;
    for (let i = di - 1; i >= 0; i--) {
      const pos = result.indexOf(defaults[i]);
      if (pos !== -1) { at = pos + 1; break; }
    }
    result.splice(at, 0, id);
  }
  return result;
}

export default function Transactions() {
  const { personId, persona, people } = usePersona();
  const { currency } = useCurrency();
  const [data, setData] = useState<Transaction[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  // Allow deep-linking a category filter, e.g. /transactions?category=Uncategorized
  // from the Overview uncategorized badge. Read once at mount (BrowserRouter keeps
  // window.location in sync after a <Link> navigation).
  const [category, setCategory] = useState(
    () => new URLSearchParams(window.location.search).get("category") ?? "all",
  );
  const [include, setInclude] = useState<IncludeFilter>("all");
  const [ccyFilter, setCcyFilter] = useState<string>("all");

  const [pairs, setPairs] = useState<TransferPair[]>([]);

  // Excel-like grid state: column order + per-column widths, persisted per device.
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(() => loadJSON(ORDER_KEY, [] as string[]));
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>(() => loadJSON(SIZE_KEY, {}));
  const dragCol = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    getTransactions({ personId, display: currency }).then((d) => alive && setData(d)).catch(() => alive && setData([]));
    getTransferPairs(personId).then((p) => alive && setPairs(p)).catch(() => alive && setPairs([]));
    return () => { alive = false; };
  }, [personId, currency]);

  const isJoint = persona === "joint";

  // Keep the persisted order coherent with the columns that currently exist.
  useEffect(() => {
    setColumnOrder((prev) => reconcileOrder(defaultOrder(isJoint), prev));
  }, [isJoint]);
  useEffect(() => { saveJSON(ORDER_KEY, columnOrder); }, [columnOrder]);
  useEffect(() => { saveJSON(SIZE_KEY, columnSizing); }, [columnSizing]);

  // Exclude both sides of a detected transfer, then refresh the list + suggestions.
  const excludePair = async (p: TransferPair) => {
    const ids = [p.out_id, p.in_id].filter((x): x is number => x != null);
    await Promise.all(ids.map((id) => updateTransaction(id, { included: false })));
    const [txns, next] = await Promise.all([getTransactions({ personId, display: currency }), getTransferPairs(personId)]);
    setData(txns);
    setPairs(next);
  };

  // Only suggest pairs whose sides are still both counted (nothing to do otherwise).
  const openPairs = pairs.filter((p) => p.both_included);

  const categories = useMemo(
    () => Array.from(new Set(data.map((t) => t.category))).sort(),
    [data],
  );

  // Write through: PATCH, then replace the row in place from the response.
  const patch = (id: number, body: { category?: string; included?: boolean }) =>
    updateTransaction(id, body)
      .then((row) => setData((d) => d.map((t) => (t.id === id ? { ...t, ...row } : t))))
      .catch(() => {});

  const rows = useMemo(
    () =>
      data.filter(
        (t) =>
          (category === "all" || t.category === category) &&
          (include === "all" || (include === "in" ? t.included === 1 : t.included === 0)) &&
          (ccyFilter === "all" || t.original_currency === ccyFilter),
      ),
    [data, category, include, ccyFilter],
  );

  // Sizes (px) sum to roughly the content width so the grid fills the window on a
  // typical screen; Description is the greedy column and truncates with ellipsis.
  // Drag a column border to resize (1:1), drag a header to reorder.
  const columns = useMemo<ColumnDef<Transaction>[]>(() => {
    const cols: ColumnDef<Transaction>[] = [
      {
        accessorKey: "date",
        header: "Date",
        size: 100,
        minSize: 76,
        cell: (c) => <span style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>{c.getValue<string>()}</span>,
      },
      {
        accessorKey: "description",
        header: "Description",
        size: 560,
        minSize: 140,
        cell: (c) => {
          const v = c.getValue<string>();
          return <span title={v} style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v}</span>;
        },
      },
    ];
    if (isJoint) {
      cols.push({
        accessorKey: "person",
        header: "Person",
        enableSorting: false,
        size: 140,
        minSize: 90,
        cell: (c) => (
          <span title={c.getValue<string>()} style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <span style={{ flex: "none", width: 8, height: 8, borderRadius: 999, background: personaColor(c.row.original.person_id, people) }} />
            {c.getValue<string>()}
          </span>
        ),
      });
    }
    cols.push(
      {
        accessorKey: "category",
        header: "Category",
        enableSorting: false,
        size: 180,
        minSize: 110,
        cell: (c) => {
          const row = c.row.original;
          return (
            <input
              list="hf-categories"
              defaultValue={row.category}
              aria-label={`Category for ${row.description}`}
              onBlur={(e) => {
                const v = e.target.value.trim();
                if (v && v !== row.category) patch(row.id, { category: v });
              }}
              style={{ ...pill, padding: "4px 10px", width: "100%", minWidth: 0 }}
            />
          );
        },
      },
      {
        accessorKey: "amount",
        header: "Amount",
        size: 128,
        minSize: 90,
        cell: (c) => <div style={{ textAlign: "right" }}><Money value={c.getValue<number>()} colored rateMissing={c.row.original.rate_stale} /></div>,
      },
      {
        id: "original",
        header: "Original",
        enableSorting: false,
        size: 116,
        minSize: 76,
        cell: (c) => {
          const t = c.row.original;
          if (t.original_currency === currency) return <span style={{ color: "var(--fl-muted)" }}>—</span>;
          return (
            <span style={{ color: "var(--fl-muted)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
              {formatMoney(t.original_amount, t.original_currency)}
            </span>
          );
        },
      },
      {
        accessorKey: "included",
        header: "In",
        enableSorting: false,
        size: 52,
        minSize: 44,
        maxSize: 72,
        cell: (c) => {
          const row = c.row.original;
          return (
            <div style={{ textAlign: "center" }}>
              <input
                type="checkbox"
                checked={row.included === 1}
                aria-label={`Include ${row.description}`}
                onChange={(e) => patch(row.id, { included: e.target.checked })}
              />
            </div>
          );
        },
      },
    );
    return cols;
  }, [isJoint, people, currency]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, globalFilter: search, columnOrder, columnSizing },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearch,
    onColumnOrderChange: setColumnOrder,
    onColumnSizingChange: setColumnSizing,
    columnResizeMode: "onChange",
    enableColumnResizing: true,
    globalFilterFn: (row, _id, value) => {
      const q = String(value).toLowerCase();
      return (
        row.original.description.toLowerCase().includes(q) ||
        row.original.category.toLowerCase().includes(q)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const visible = table.getRowModel().rows;
  const leafColumns = table.getVisibleLeafColumns();

  // Drop the dragged header before the one it's released on, and persist.
  // ponytail: reorder uses native HTML5 drag-and-drop (no new dependency).
  // Ceiling: pointer-only — no keyboard reorder/resize. Upgrade path if needed:
  // @dnd-kit (TanStack's column-DnD example) adds keyboard + smooth dragging.
  const moveColumn = (to: string) => {
    const from = dragCol.current;
    dragCol.current = null;
    if (!from || from === to) return;
    setColumnOrder((prev) => {
      const base = prev.length ? prev : defaultOrder(isJoint);
      const next = base.filter((id) => id !== from);
      next.splice(next.indexOf(to), 0, from);
      return next;
    });
  };

  return (
    // minmax(0,1fr) caps the single column at the container width so a wide table
    // scrolls inside its own card instead of stretching the whole page (grid items
    // default to min-width:auto, which would otherwise grow to the table's width).
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Transactions</h1>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} style={pill} />
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={pill}>
            <option value="all">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={include} onChange={(e) => setInclude(e.target.value as IncludeFilter)} style={pill}>
            <option value="all">All</option>
            <option value="in">Included</option>
            <option value="out">Excluded</option>
          </select>
          <select value={ccyFilter} onChange={(e) => setCcyFilter(e.target.value)} style={pill}>
            <option value="all">Any currency</option>
            <option value="ILS">₪ entered</option>
            <option value="USD">$ entered</option>
          </select>
        </div>
      </header>

      <datalist id="hf-categories">
        {categories.map((c) => <option key={c} value={c} />)}
      </datalist>

      {openPairs.length > 0 && (
        <section aria-label="Transfer pairs" className="frosted-card" style={{ padding: 16, display: "grid", gap: 10 }}>
          <div style={{ fontSize: 13 }}>
            <strong>{openPairs.length} transfer {openPairs.length === 1 ? "pair" : "pairs"} detected.</strong>{" "}
            <span style={{ color: "var(--fl-muted)" }}>Money moved between accounts isn't spend or income — exclude both sides so it doesn't double-count.</span>
          </div>
          {openPairs.map((p, i) => (
            <div key={`${p.out_id}-${p.in_id}-${i}`} style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 13 }}>
              <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                <Money
                  value={-(p.out_amount ?? p.amount)}
                  currency={(p.out_currency as import("@/lib/currency").Currency) ?? "USD"}
                  colored
                />
                {" → "}
                <Money
                  value={p.in_amount ?? p.amount}
                  currency={(p.in_currency as import("@/lib/currency").Currency) ?? "USD"}
                  colored
                />
              </span>
              <span style={{ color: "var(--fl-muted)" }}>{p.out_desc} → {p.in_desc}</span>
              {p.cross_person && <span style={{ ...pill, padding: "2px 8px", fontSize: 11 }}>cross-person</span>}
              <button onClick={() => excludePair(p)} style={{ ...pill, marginLeft: "auto", fontWeight: 700, color: "var(--persona-solid)" }}>
                Exclude both
              </button>
            </div>
          ))}
        </section>
      )}

      {/* Spreadsheet viewport: a fixed-height scroll region you pan in both
          directions (like Excel), with the header row frozen at the top. The
          table sizes to its columns, so a too-wide grid scrolls here instead of
          widening the page. */}
      <section className="frosted-card" style={{ padding: 8 }}>
        <div style={{ overflow: "auto", maxHeight: "calc(100vh - 230px)", borderRadius: 10 }}>
          <table style={{ width: table.getTotalSize(), minWidth: "100%", borderCollapse: "collapse", tableLayout: "fixed", fontSize: 14 }}>
            <colgroup>
              {leafColumns.map((col) => <col key={col.id} style={{ width: col.getSize() }} />)}
            </colgroup>
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const sortable = h.column.getCanSort();
                    const dir = h.column.getIsSorted();
                    const right = h.column.id === "amount";
                    return (
                      <th
                        key={h.id}
                        style={{
                          position: "sticky", top: 0, zIndex: 1, background: "var(--fl-card)",
                          textAlign: right ? "right" : "left",
                          padding: "0 10px", height: 38,
                          borderBottom: "1px solid var(--fl-line)", borderRight: "1px solid var(--fl-line)",
                          color: dir ? "var(--persona-solid)" : "var(--fl-muted)",
                          textTransform: "uppercase", fontSize: 11, letterSpacing: "0.06em", fontWeight: 700,
                        }}
                      >
                        <span
                          draggable
                          onDragStart={() => { dragCol.current = h.column.id; }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => moveColumn(h.column.id)}
                          onClick={sortable ? h.column.getToggleSortingHandler() : undefined}
                          title="Drag to reorder"
                          style={{
                            display: "inline-flex", alignItems: "center", gap: 4, maxWidth: "100%",
                            cursor: sortable ? "pointer" : "grab", userSelect: "none",
                          }}
                        >
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {flexRender(h.column.columnDef.header, h.getContext())}
                          </span>
                          {dir === "asc" ? "▲" : dir === "desc" ? "▼" : ""}
                        </span>
                        {h.column.getCanResize() && (
                          <div
                            onMouseDown={h.getResizeHandler()}
                            onTouchStart={h.getResizeHandler()}
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              position: "absolute", top: 0, right: 0, height: "100%", width: 6,
                              cursor: "col-resize", touchAction: "none", userSelect: "none",
                              background: h.column.getIsResizing() ? "var(--persona-solid)" : "transparent",
                            }}
                          />
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {visible.map((r) => {
                const muted = r.original.included === 0;
                return (
                  <tr
                    key={r.id}
                    style={{
                      opacity: muted ? 0.45 : 1,
                      boxShadow: isJoint ? `inset 3px 0 0 0 ${personaColor(r.original.person_id, people)}` : undefined,
                    }}
                  >
                    {r.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        style={{
                          padding: "8px 10px", height: 40,
                          borderBottom: "1px solid var(--fl-line)", borderRight: "1px solid var(--fl-line)",
                          overflow: "hidden", whiteSpace: "nowrap",
                        }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {visible.length === 0 && (
            <p style={{ color: "var(--fl-muted)", padding: 24, textAlign: "center" }}>No transactions match these filters.</p>
          )}
        </div>
      </section>
    </div>
  );
}
