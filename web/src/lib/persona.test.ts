import { expect, test } from "vitest";
import { personaFill, personaSolid } from "./persona";

test("Joint persona fill resolves to the gradient, never blue", () => {
  expect(personaFill("joint")).toBe("var(--persona-joint)");
  expect(personaFill("joint")).not.toBe("var(--persona-you)");
});

test("single personas resolve to their own ink", () => {
  expect(personaFill("you")).toBe("var(--persona-you)");
  expect(personaFill("spouse")).toBe("var(--persona-spouse)");
});

test("Joint solid companion is the violet stand-in, not blue", () => {
  expect(personaSolid("joint")).toBe("var(--persona-joint-solid)");
  expect(personaSolid("joint")).not.toBe("var(--persona-you)");
});

test("single-persona solid matches its fill (no gradient needed)", () => {
  expect(personaSolid("you")).toBe("var(--persona-you)");
  expect(personaSolid("spouse")).toBe("var(--persona-spouse)");
});
