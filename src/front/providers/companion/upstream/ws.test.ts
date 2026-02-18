import { describe, it, expect, vi } from "vitest";

vi.mock("../config.js", () => ({
  getCompanionBaseUrl: vi.fn(),
  getCompanionAuthToken: vi.fn(),
}));

import { getCompanionBaseUrl, getCompanionAuthToken } from "../config.js";
import { __companionWsTestUtils } from "./ws.js";

describe("companion upstream ws URL", () => {
  it("rewrites legacy /ws/browser/{id} to canonical /ws/agent/companion/browser/{id}", () => {
    vi.mocked(getCompanionBaseUrl).mockReturnValue("https://companion.example/cc/");
    vi.mocked(getCompanionAuthToken).mockReturnValue("test-token");
    expect(__companionWsTestUtils.getWsUrl("sess-1")).toBe(
      "wss://companion.example/cc/ws/agent/companion/browser/sess-1?token=test-token",
    );
  });

  it("omits token query string when token is not set", () => {
    vi.mocked(getCompanionBaseUrl).mockReturnValue("http://companion.example");
    vi.mocked(getCompanionAuthToken).mockReturnValue("");
    expect(__companionWsTestUtils.getWsUrl("sess-2")).toBe(
      "ws://companion.example/ws/agent/companion/browser/sess-2",
    );
  });
});
