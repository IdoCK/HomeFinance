import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { getTransactions, updateTransaction, type Transaction } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money } from "@/components/money";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type IncludeFilter = "all" | "in" | "out";
type Person = { id: number; name: string };

// ponytail: persona colors are keyed by people[0]/[1] (You/Spouse). Ceiling: only the
// first two people get a signature color; a third+ person falls back to the hairline.
const personaColor = (personId: number, people: Person[]) =>
  personId === people[0]?.id ? "var(--persona-you)"
  : personId === people[1]?.id ? "var(--persona-spouse)"
  : "var(--fl-line)";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};

export default function Transactions() {
  const { personId, persona, people } = usePersona();
  const [data, setData] = useState<Transaction[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [include, setInclude] = useState<IncludeFilter>("all");

  useEffect(() => {
    let alive = true;
    getTransactions({ personId }).then((d) => alive && setData(d)).catch(() => alive && setData([]));
    return () => { alive = false; };
  }, [personId]);

  const isJoint = persona === "joint";

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
          (include === "all" || (include === "in" ? t.included === 1 : t.included === 0)),
      ),
    [data, category, include],
  );

  const columns = useMemo<ColumnDef<Transaction>[]>(() => {
    const cols: ColumnDef<Transaction>[] = [
      {
        accessorKey: "date",
        header: "Date",
        cell: (c) => <span style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>{c.getValue<string>()}</span>,
      },
      { accessorKey: "description", header: "Description" },
    ];
    if (isJoint) {
      cols.push({
        accessorKey: "person",
        header: "Person",
        enableSorting: false,
        cell: (c) => (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: personaColor(c.row.original.person_id, people) }} />
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
              style={{ ...pill, padding: "4px 10px", maxWidth: 160 }}
            />
          );
        },
      },
      {
        accessorKey: "amount",
        header: "Amount",
        cell: (c) => <div style={{ textAlign: "right" }}><Money value={c.getValue<number>()} colored /></div>,
      },
      {
        accessorKey: "included",
        header: "In",
        enableSorting: false,
        cell: (c) => {
          const row = c.row.original;
          return (
            <input
              type="checkbox"
              checked={row.included === 1}
              aria-label={`Include ${row.description}`}
              onChange={(e) => patch(row.id, { included: e.target.checked })}
            />
          );
        },
      },
    );
    return cols;
  }, [isJoint, people]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, globalFilter: search },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearch,
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

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Transactions</h1>
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
        </div>
      </header>

      <datalist id="hf-categories">
        {categories.map((c) => <option key={c} value={c} />)}
      </datalist>

      <section className="frosted-card" style={{ padding: 8 }}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => {
                  const sortable = h.column.getCanSort();
                  const dir = h.column.getIsSorted();
                  return (
                    <TableHead
                      key={h.id}
                      onClick={sortable ? h.column.getToggleSortingHandler() : undefined}
                      style={{
                        cursor: sortable ? "pointer" : "default",
                        textAlign: h.column.id === "amount" ? "right" : "left",
                        color: dir ? "var(--persona)" : "var(--fl-muted)",
                        userSelect: "none", textTransform: "uppercase", fontSize: 11, letterSpacing: "0.06em",
                      }}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {dir === "asc" ? " ▲" : dir === "desc" ? " ▼" : ""}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {visible.map((r) => {
              const muted = r.original.included === 0;
              return (
                <TableRow
                  key={r.id}
                  style={{
                    opacity: muted ? 0.45 : 1,
                    boxShadow: isJoint ? `inset 3px 0 0 0 ${personaColor(r.original.person_id, people)}` : undefined,
                  }}
                >
                  {r.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {visible.length === 0 && (
          <p style={{ color: "var(--fl-muted)", padding: 24, textAlign: "center" }}>No transactions match these filters.</p>
        )}
      </section>
    </div>
  );
}
