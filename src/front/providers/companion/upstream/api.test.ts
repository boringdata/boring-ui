import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../config.js", () => ({
  getCompanionBaseUrl: () => "http://companion.example/base",
  getAuthHeaders: () => ({ Authorization: "Bearer test-token" }),
}));

import { api } from "./api.js";

describe("companion upstream api base URL", () => {
  beforeEach(() => {
    (globalThis as unknown as { fetch: unknown }).fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
  });

  it("uses canonical /api/v1/agent/companion prefix when COMPANION_URL is set", async () => {
    await api.listSessions();

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledWith(
      "http://companion.example/base/api/v1/agent/companion/sessions",
      { headers: { Authorization: "Bearer test-token" } },
    );
  });
});

