import { NavLink } from "react-router-dom";
import { usePersona, type PersonaKey } from "@/lib/persona";
import { useTheme } from "@/lib/theme";

const NAV: { to: string; label: string }[] = [
  { to: "/", label: "Overview" },
  { to: "/transactions", label: "Transactions" },
  { to: "/budgets", label: "Budgets" },
  { to: "/recurring", label: "Recurring" },
  { to: "/goals", label: "Goals" },
  { to: "/networth", label: "Net Worth" },
  { to: "/events", label: "Events" },
  { to: "/import", label: "＋ Import" },
  { to: "/insights", label: "AI Insights" },
  { to: "/settings", label: "Settings" },
];

const PERSONAS: { key: PersonaKey; text: string }[] = [
  { key: "you", text: "Ido" },
  { key: "spouse", text: "Aviv" },
  { key: "joint", text: "Joint" },
];

export function AppSidebar() {
  const { persona, setPersona, names } = usePersona();
  const { theme, toggle } = useTheme();
  const text = (k: PersonaKey) =>
    k === "you" ? names.you : k === "spouse" ? names.spouse : "Joint";

  return (
    <aside data-persona-seam={persona} style={{ width: 232, padding: 16, borderRight: "1px solid var(--fl-line)" }}>
      <div role="tablist" aria-label="Persona" style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {PERSONAS.map((p) => (
          <button
            key={p.key}
            role="tab"
            aria-selected={persona === p.key}
            onClick={() => setPersona(p.key)}
            style={{
              flex: 1, padding: "6px 8px", borderRadius: 999, fontSize: 13,
              border: "1px solid var(--fl-line)",
              background: persona === p.key ? "var(--persona)" : "transparent",
              color: persona === p.key ? "#fff" : "var(--fl-ink)",
            }}
          >
            {text(p.key)}
          </button>
        ))}
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            style={({ isActive }) => ({
              padding: "8px 12px", borderRadius: 10, textDecoration: "none",
              color: isActive ? "var(--persona)" : "var(--fl-ink)",
              background: isActive ? "color-mix(in srgb, var(--persona) 10%, transparent)" : "transparent",
              fontWeight: isActive ? 700 : 500,
            })}
          >
            {n.label}
          </NavLink>
        ))}
      </nav>

      <button onClick={toggle} style={{ marginTop: 24, fontSize: 13, color: "var(--fl-muted)", background: "none", border: "none", cursor: "pointer" }}>
        {theme === "dark" ? "☀ Light" : "☾ Dark"}
      </button>
    </aside>
  );
}
