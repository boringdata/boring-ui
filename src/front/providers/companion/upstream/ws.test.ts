import { describe, it, expect, vi } from "vitest";

vi.mock("../config.js", () => ({
  getCompanionBaseUrl: () => "https://companion.example/cc/",
  getCompanionAuthToken: () => "test-token",
}));

import { __companionWsTestUtils } from "./ws.js";

describe("companion upstream ws URL", () => {
  it("rewrites legacy /ws/browser/{id} to canonical /ws/agent/companion/browser/{id}", () => {
    expect(__companionWsTestUtils.getWsUrl("sess-1")).toBe(
      "wss://companion.example/cc/ws/agent/companion/browser/sess-1?token=test-token",
    );
  });
});

