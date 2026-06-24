import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getPeople, type Person } from "./api";

export type PersonaKey = "you" | "spouse" | "joint";

type PersonaCtx = {
  persona: PersonaKey;
  setPersona: (p: PersonaKey) => void;
  personId?: number;
  people: Person[];
  label: string;
  /** Display name for each single-person persona (sidebar tabs, headers). */
  names: { you: string; spouse: string };
};

const Ctx = createContext<PersonaCtx | null>(null);

/** The fill for a persona — a real color for single people, the blue→pink
 *  GRADIENT for Joint. Use only as a `background` (a gradient is not a valid
 *  color value for text/stroke/border). Joint NEVER resolves to blue. */
export function personaFill(persona: PersonaKey): string {
  return persona === "spouse" ? "var(--persona-spouse)"
    : persona === "joint" ? "var(--persona-joint)"
    : "var(--persona-you)";
}

/** A guaranteed-solid companion color for a persona (text/stroke/border/SVG).
 *  Joint uses the violet mid-point stand-in (`--persona-joint-solid`), never the
 *  blue "you" ink. */
export function personaSolid(persona: PersonaKey): string {
  return persona === "spouse" ? "var(--persona-spouse)"
    : persona === "joint" ? "var(--persona-joint-solid)"
    : "var(--persona-you)";
}

// Canonical household identity: Ido is the primary persona ("you" / blue),
// Aviv the secondary ("spouse" / pink). We resolve each persona to its person
// by NAME, not by row position: the live DB orders people by id as
// [Aviv(id1), Ido(id2)], so positional mapping would wire Aviv (the only user
// with data) to the blue "you" accent and Ido to pink — inverting the locked
// design. A positional fallback keeps fresh/renamed DBs (and tests) working.
const PRIMARY_NAME = "Ido";
const SECONDARY_NAME = "Aviv";

function resolvePerson(people: Person[], key: "you" | "spouse"): Person | undefined {
  const name = key === "you" ? PRIMARY_NAME : SECONDARY_NAME;
  return people.find((p) => p.name === name) ?? (key === "you" ? people[0] : people[1]);
}

export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [persona, setPersona] = useState<PersonaKey>("you");

  useEffect(() => {
    getPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  useEffect(() => {
    const el = document.documentElement;
    el.dataset.persona = persona;
    // Three-way swap. --persona is a fill (may be the Joint gradient);
    // --persona-solid is its always-a-color companion for text/border/SVG.
    el.style.setProperty("--persona", personaFill(persona));
    el.style.setProperty("--persona-solid", personaSolid(persona));
  }, [persona]);

  const youPerson = resolvePerson(people, "you");
  const spousePerson = resolvePerson(people, "spouse");

  const personId =
    persona === "you" ? youPerson?.id
    : persona === "spouse" ? spousePerson?.id
    : undefined;

  const names = useMemo(
    () => ({
      you: youPerson?.name ?? PRIMARY_NAME,
      spouse: spousePerson?.name ?? SECONDARY_NAME,
    }),
    [youPerson?.name, spousePerson?.name],
  );

  const label = persona === "joint" ? "Joint" : persona === "you" ? names.you : names.spouse;

  const value = useMemo(
    () => ({ persona, setPersona, personId, people, label, names }),
    [persona, personId, people, label, names],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePersona(): PersonaCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePersona must be used within <PersonaProvider>");
  return v;
}
