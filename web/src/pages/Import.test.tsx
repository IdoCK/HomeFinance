import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

let mockPersonId: number | undefined = 1;
const getOllamaStatus = vi.fn();
const parseImport = vi.fn();
const commitImport = vi.fn();

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: mockPersonId, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getOllamaStatus: (...a: unknown[]) => getOllamaStatus(...a),
  parseImport: (...a: unknown[]) => parseImport(...a),
  commitImport: (...a: unknown[]) => commitImport(...a),
}));

import Import from "./Import";

const ROW = { date: "2026-06-01", description: "WHOLE FOODS", amount: -52.1, category: "Groceries", source: "bank", included: true, balance: null };

beforeEach(() => {
  mockPersonId = 1;
  getOllamaStatus.mockResolvedValue({ ok: true, message: "ready" });
  parseImport.mockResolvedValue({ already_imported: false, file_hash: "h", filename: "june.csv", source: "bank", rows: [ROW], warnings: [] });
  commitImport.mockResolvedValue({ imported: 1 });
});
afterEach(() => { getOllamaStatus.mockReset(); parseImport.mockReset(); commitImport.mockReset(); });

test("Joint view gates importing to a single person", async () => {
  mockPersonId = undefined;
  render(<Import />);
  expect(await screen.findByText(/switch to you or spouse/i)).toBeInTheDocument();
});

test("upload then parse advances to the review table", async () => {
  render(<Import />);
  const file = new File(["date,amt"], "june.csv", { type: "text/csv" });
  await userEvent.upload(screen.getByLabelText(/choose file/i), file);
  await userEvent.click(screen.getByRole("button", { name: /parse file/i }));
  await waitFor(() => expect(parseImport).toHaveBeenCalledWith(file, expect.any(String), 1));
  expect(await screen.findByText("WHOLE FOODS")).toBeInTheDocument();
});

test("committing the reviewed rows calls commitImport and shows the result", async () => {
  render(<Import />);
  const file = new File(["date,amt"], "june.csv", { type: "text/csv" });
  await userEvent.upload(screen.getByLabelText(/choose file/i), file);
  await userEvent.click(screen.getByRole("button", { name: /parse file/i }));
  await screen.findByText("WHOLE FOODS");
  await userEvent.click(screen.getByRole("button", { name: /import 1 transaction/i }));
  await waitFor(() => expect(commitImport).toHaveBeenCalledWith(expect.objectContaining({
    personId: 1, filename: "june.csv", fileHash: "h", rows: [ROW],
  })));
  expect(await screen.findByText(/imported 1 transaction/i)).toBeInTheDocument();
});

test("an already-imported file is flagged, not re-reviewed", async () => {
  parseImport.mockResolvedValue({ already_imported: true, file_hash: "h", filename: "june.csv", source: "bank", rows: [], warnings: [] });
  render(<Import />);
  const file = new File(["date,amt"], "june.csv", { type: "text/csv" });
  await userEvent.upload(screen.getByLabelText(/choose file/i), file);
  await userEvent.click(screen.getByRole("button", { name: /parse file/i }));
  expect(await screen.findByText(/already imported/i)).toBeInTheDocument();
});
