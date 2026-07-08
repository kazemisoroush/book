import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/config", () => ({
  loadConfig: vi.fn(async () => ({ apiUrl: "http://api.test" })),
}));

import { apiClient } from "./client";

function mockLocation(pathname: string) {
  const assign = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname, assign },
  });
  return assign;
}

describe("apiClient", () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    vi.unstubAllGlobals();
  });

  it("redirects to /login when the API returns 401", async () => {
    const assign = mockLocation("/");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"message":"Unauthorized"}', { status: 401 })),
    );

    const client = await apiClient();
    await client.GET("/books");

    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("does not redirect on a successful response", async () => {
    const assign = mockLocation("/");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response('{"books":[]}', {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
      ),
    );

    const client = await apiClient();
    await client.GET("/books");

    expect(assign).not.toHaveBeenCalled();
  });
});
