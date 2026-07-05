import { describe, expect, it } from "vitest";

import { parseBookId } from "./books";

describe("parseBookId", () => {
  it("humanizes a title:author slug", () => {
    expect(parseBookId("the_gambler:fyodor_dostoyevsky")).toEqual({
      id: "the_gambler:fyodor_dostoyevsky",
      title: "The Gambler",
      author: "Fyodor Dostoyevsky",
    });
  });

  it("falls back to Unknown when the author is missing", () => {
    expect(parseBookId("the_odyssey")).toEqual({
      id: "the_odyssey",
      title: "The Odyssey",
      author: "Unknown",
    });
  });
});
