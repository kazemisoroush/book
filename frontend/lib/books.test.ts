import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
}));

import { apiClient } from "@/lib/api/client";
import { fetchBooks, parseBookId } from "./books";

describe("parseBookId", () => {
  it("humanizes a title:author slug", () => {
    expect(parseBookId("the_gambler:fyodor_dostoyevsky")).toEqual({
      title: "The Gambler",
      author: "Fyodor Dostoyevsky",
    });
  });

  it("falls back to Unknown when the author is missing", () => {
    expect(parseBookId("the_odyssey")).toEqual({
      title: "The Odyssey",
      author: "Unknown",
    });
  });
});

describe("fetchBooks", () => {
  it("shapes the API metadata, defaulting a missing author", async () => {
    vi.mocked(apiClient).mockResolvedValue({
      GET: vi.fn().mockResolvedValue({
        data: {
          books: [
            {
              id: "wuthering_heights:emily_bront",
              title: "Wuthering Heights",
              author: "Emily Brontë",
              language: "en",
              release_date: "1996-12-01",
              chapters: 1,
              characters: 3,
              cast: 0,
            },
            {
              id: "the_odyssey:homer",
              title: "The Odyssey",
              author: null,
              language: null,
              release_date: null,
              chapters: 24,
              characters: 40,
              cast: 2,
            },
          ],
        },
        error: undefined,
      }),
    } as never);

    const books = await fetchBooks();

    expect(books[0]).toEqual({
      id: "wuthering_heights:emily_bront",
      title: "Wuthering Heights",
      author: "Emily Brontë",
      language: "en",
      releaseDate: "1996-12-01",
      chapters: 1,
      characters: 3,
      cast: 0,
    });
    expect(books[1].author).toBe("Unknown");
    expect(books[1].language).toBeUndefined();
  });
});
