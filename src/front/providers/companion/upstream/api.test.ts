import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../config.js", () => ({
  getCompanionBaseUrl: vi.fn(),
  getAuthHeaders: vi.fn(),
}));

import { getCompanionBaseUrl, getAuthHeaders } from "../config.js";
import { api } from "./api.js";

describe("companion upstream api base URL", () => {
  beforeEach(() => {
    vi.mocked(getCompanionBaseUrl).mockReturnValue("http://companion.example/base");
    vi.mocked(getAuthHeaders).mockReturnValue({ Authorization: "Bearer test-token" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("uses canonical /api/v1/agent/companion prefix when COMPANION_URL is set", async () => {
    await api.listSessions();

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledWith(
      "http://companion.example/base/api/v1/agent/companion/sessions",
      { headers: { Authorization: "Bearer test-token" } },
    );
  });

  it("normalizes trailing slashes on COMPANION_URL", async () => {
    vi.mocked(getCompanionBaseUrl).mockReturnValue("http://companion.example/base/");

    await api.listSessions();

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledWith(
      "http://companion.example/base/api/v1/agent/companion/sessions",
      { headers: { Authorization: "Bearer test-token" } },
    );
  });

  it("uses canonical same-origin prefix when COMPANION_URL is not set", async () => {
    vi.mocked(getCompanionBaseUrl).mockReturnValue("");

    await api.listSessions();

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/agent/companion/sessions",
      { headers: { Authorization: "Bearer test-token" } },
    );
  });
});
