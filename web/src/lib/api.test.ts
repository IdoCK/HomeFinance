import { afterEach, expect, test, vi } from "vitest";
import { getOverview } from "./api";

afterEach(() => vi.restoreAllMocks());

test("getOverview builds /api/overview with person_id+month and returns JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ month: "2026-05", months: ["2026-05"], income: 10, spend: 4, net: 6, savings_rate: 0.6, complete: true, by_category: { Rent: 4 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const d = await getOverview({ personId: 1, month: "2026-05" });

  const url = fetchMock.mock.calls[0][0] as string;
  expect(url).toBe("/api/overview?person_id=1&month=2026-05");
  expect(d.net).toBe(6);
});

test("getOverview omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);
  await getOverview({});
  expect(fetchMock.mock.calls[0][0]).toBe("/api/overview");
});
