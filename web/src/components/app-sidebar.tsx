import { NavLink } from "react-router-dom";
import {
  LayoutGrid, List, BarChart3, PieChart, RefreshCw, Target, TrendingUp, Tag,
  Plus, Sparkles, Settings as SettingsIcon, BookOpen, type LucideIcon,
} from "lucide-react";
import { usePersona, type PersonaKey } from "@/lib/persona";
import { useTheme } from "@/lib/theme";
import { useCurrency, type Currency } from "@/lib/currency";

type NavItem = { to: string; label: string; Icon: LucideIcon; important?: boolean };

// Two groups matching the reference: the "Money" surfaces, then "Utility".
const MONEY: NavItem[] = [
  { to: "/", label: "Overview", Icon: LayoutGrid },
  { to: "/transactions", label: "Transactions", Icon: List },
  { to: "/analysis", label: "Analysis", Icon: BarChart3 },
  { to: "/budgets", label: "Budgets", Icon: PieChart },
  { to: "/recurring", label: "Recurring", Icon: RefreshCw },
  { to: "/goals", label: "Goals", Icon: Target },
  { to: "/networth", label: "Net Worth", Icon: TrendingUp },
  { to: "/events", label: "Events", Icon: Tag },
];
const UTILITY: NavItem[] = [
  { to: "/import", label: "Import", Icon: Plus, important: true },
  { to: "/insights", label: "AI Insights", Icon: Sparkles },
  { to: "/settings", label: "Settings", Icon: SettingsIcon },
  { to: "/guide", label: "User Guide", Icon: BookOpen },
];

const PERSONA_KEYS: { key: PersonaKey; dot: string }[] = [
  { key: "you", dot: "var(--persona-you)" },
  { key: "spouse", dot: "var(--persona-spouse)" },
  { key: "joint", dot: "conic-gradient(from 220deg, var(--persona-you), var(--persona-spouse))" },
];

export function AppSidebar() {
  const { persona, setPersona, names } = usePersona();
  const { theme, toggle } = useTheme();
  const { currency, setCurrency } = useCurrency();
  const CURRENCIES: { key: Currency; label: string }[] = [
    { key: "USD", label: "$ USD" },
    { key: "ILS", label: "₪ ILS" },
  ];
  const text = (k: PersonaKey) => (k === "you" ? names.you : k === "spouse" ? names.spouse : "Joint");

  return (
    <aside
      data-persona-seam={persona}
      style={{
        width: 224, padding: "18px 14px", display: "flex", flexDirection: "column", gap: 4,
        flex: "none", height: "100vh", overflowY: "auto",
        background: "var(--fl-frame)",
      }}
    >
      {/* Brand */}
      <div style={{ display: "flex", alignItems: "center", gap: 9, fontWeight: 800, fontSize: 16, letterSpacing: "-0.02em", padding: "2px 6px 14px" }}>
        <span style={{ width: 24, height: 24, borderRadius: 8, background: "linear-gradient(135deg,#FBBF24,#EC4899 55%,#3B82F6)", boxShadow: "0 4px 10px -3px rgba(236,72,153,.53)" }} />
        Household
      </div>

      {/* Persona segmented switch */}
      <div role="tablist" aria-label="Persona" style={{ display: "flex", gap: 4, background: "#EEF0F3", borderRadius: 14, padding: 4, margin: "0 2px 16px" }}>
        {PERSONA_KEYS.map((p) => {
          const active = persona === p.key;
          return (
            <button
              key={p.key}
              role="tab"
              aria-selected={active}
              onClick={() => setPersona(p.key)}
              style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                fontSize: 11.5, fontWeight: 600, padding: "7px 0", borderRadius: 10, border: "none", cursor: "pointer",
                background: active ? "#fff" : "transparent",
                color: active ? "var(--fl-ink)" : "var(--fl-muted)",
                boxShadow: active ? "0 2px 8px -2px rgba(22,24,29,.18)" : "none",
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.dot }} />
              {text(p.key)}
            </button>
          );
        })}
      </div>

      {/* Display-currency segmented switch (sibling of the persona switch) */}
      <div role="tablist" aria-label="Display currency" style={{ display: "flex", gap: 4, background: "#EEF0F3", borderRadius: 14, padding: 4, margin: "0 2px 16px" }}>
        {CURRENCIES.map((c) => {
          const active = currency === c.key;
          return (
            <button
              key={c.key} role="tab" aria-selected={active} onClick={() => setCurrency(c.key)}
              style={{
                flex: 1, fontSize: 11.5, fontWeight: 600, padding: "7px 0", borderRadius: 10,
                border: "none", cursor: "pointer",
                background: active ? "#fff" : "transparent",
                color: active ? "var(--fl-ink)" : "var(--fl-muted)",
                boxShadow: active ? "0 2px 8px -2px rgba(22,24,29,.18)" : "none",
              }}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      <NavGroup label="Money" items={MONEY} />
      <div style={{ height: 1, background: "var(--fl-line)", margin: "10px 8px" }} />
      <NavGroup label="Utility" items={UTILITY} />

      <button
        onClick={toggle}
        style={{ marginTop: "auto", fontSize: 10.5, color: "var(--fl-muted)", background: "none", border: "none", cursor: "pointer", padding: 8, textAlign: "left", display: "flex", alignItems: "center", gap: 6 }}
      >
        🔒 Local only · {theme === "dark" ? "☀ Light mode" : "☾ Dark mode"}
      </button>
    </aside>
  );
}

function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  return (
    <>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#94A3B8", margin: "8px 8px 4px" }}>
        {label}
      </div>
      <nav style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {items.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            style={({ isActive }) => ({
              display: "flex", alignItems: "center", gap: 11, fontSize: 13,
              padding: "9px 11px", borderRadius: 11, textDecoration: "none",
              fontWeight: isActive ? 600 : n.important ? 700 : 500,
              background: isActive ? "var(--fl-ink)" : "transparent",
              color: isActive ? "#fff" : n.important ? "var(--persona-you-deep)" : "#4B5059",
              boxShadow: isActive ? "0 8px 18px -8px rgba(22,24,29,.6)" : "none",
            })}
          >
            <n.Icon size={16} strokeWidth={2} aria-hidden style={{ flex: "none", opacity: 0.85 }} />
            {n.label}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
