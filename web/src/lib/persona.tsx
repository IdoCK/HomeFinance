import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getPeople, type Person } from "./api";

export type PersonaKey = "you" | "spouse" | "joint";

type PersonaCtx = {
  persona: PersonaKey;
  setPersona: (p: PersonaKey) => void;
  personId?: number;
  people: Person[];
  label: string;
};

const Ctx = createContext<PersonaCtx | null>(null);

export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [persona, setPersona] = useState<PersonaKey>("you");

  useEffect(() => {
    getPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  useEffect(() => {
    const el = document.documentElement;
    el.dataset.persona = persona;
    el.style.setProperty(
      "--persona",
      persona === "spouse" ? "var(--persona-spouse)" : "var(--persona-you)",
    );
  }, [persona]);

  const personId =
    persona === "you" ? people[0]?.id
    : persona === "spouse" ? people[1]?.id
    : undefined;

  const label =
    persona === "joint" ? "Joint"
    : (persona === "you" ? people[0]?.name : people[1]?.name) ?? (persona === "you" ? "You" : "Spouse");

  const value = useMemo(
    () => ({ persona, setPersona, personId, people, label }),
    [persona, personId, people, label],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePersona(): PersonaCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePersona must be used within <PersonaProvider>");
  return v;
}
