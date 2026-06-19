import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { PersonaProvider, usePersona } from "./persona";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const { label, personId, setPersona } = usePersona();
  return (
    <div>
      <span data-testid="label">{label}</span>
      <span data-testid="pid">{personId ?? "none"}</span>
      <button onClick={() => setPersona("spouse")}>spouse</button>
      <button onClick={() => setPersona("joint")}>joint</button>
    </div>
  );
}

test("maps personas to person_id and recolors via --persona", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, json: async () => [{ id: 7, name: "Ada" }, { id: 9, name: "Mara" }],
  }));
  render(<PersonaProvider><Probe /></PersonaProvider>);

  await waitFor(() => expect(screen.getByTestId("label")).toHaveTextContent("Ada"));
  expect(screen.getByTestId("pid")).toHaveTextContent("7");
  expect(document.documentElement.dataset.persona).toBe("you");

  await userEvent.click(screen.getByText("spouse"));
  expect(screen.getByTestId("pid")).toHaveTextContent("9");
  expect(document.documentElement.dataset.persona).toBe("spouse");

  await userEvent.click(screen.getByText("joint"));
  expect(screen.getByTestId("pid")).toHaveTextContent("none");
  expect(document.documentElement.dataset.persona).toBe("joint");
});
