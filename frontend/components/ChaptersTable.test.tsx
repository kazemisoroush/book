import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/useRunLogs", () => ({
  useRunLogs: () => ({ lines: [], finalStatus: null }),
}));

vi.mock("@/lib/useBookRuns", () => ({
  useBookRuns: () => ({ runs: [], reloadRuns: vi.fn() }),
  latestRunByChapter: () => new Map(),
}));

vi.mock("@/lib/studio", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/studio")>();
  return {
    ...actual,
    startRun: vi.fn().mockResolvedValue({ run_id: "r1", workflow: "ai", state: "running" }),
  };
});

import { startRun, type ChapterSummary } from "@/lib/studio";

import { ChaptersTable } from "./ChaptersTable";

const BOOK_ID = "the_gambler:fyodor_dostoyevsky";
const URL = "https://www.gutenberg.org/cache/epub/2554/pg2554-images.zip";

const chapters: ChapterSummary[] = [
  { number: 1, title: "The garret", beats: 0 },
  { number: 2, title: "The tavern", beats: 12 },
];

// Open the ⋯ actions menu for the row at *index* and return a scoped query for its items.
function openRowMenu(index: number) {
  const triggers = screen.getAllByRole("button", { name: "Chapter actions" });
  fireEvent.click(triggers[index]);
  return within(screen.getByRole("menu"));
}

describe("ChaptersTable", () => {
  it("links each chapter title to its attribution review", () => {
    render(<ChaptersTable bookId={BOOK_ID} chapters={chapters} sourceUrl={URL} />);

    const link = screen.getByRole("link", { name: /The garret/ });
    expect(link).toHaveAttribute(
      "href",
      `/book/chapter?id=${encodeURIComponent(BOOK_ID)}&chapter=1`,
    );
    expect(screen.getByText("12 beats")).toBeInTheDocument();
  });

  it("offers Review, Extract, and Narrate from the row's ⋯ menu", () => {
    render(<ChaptersTable bookId={BOOK_ID} chapters={chapters} sourceUrl={URL} />);

    const menu = openRowMenu(0);
    expect(menu.getByRole("menuitem", { name: "Review attribution" })).toBeInTheDocument();
    expect(menu.getByRole("menuitem", { name: "Extract beats" })).toBeInTheDocument();
    expect(menu.getByRole("menuitem", { name: "Narrate" })).toBeInTheDocument();
  });

  it("extracts beats for the chapter that has none, tagged with the book", async () => {
    render(<ChaptersTable bookId={BOOK_ID} chapters={chapters} sourceUrl={URL} />);

    fireEvent.click(openRowMenu(0).getByRole("menuitem", { name: "Extract beats" }));

    await waitFor(() =>
      expect(startRun).toHaveBeenCalledWith({
        workflow: "ai",
        url: URL,
        startChapter: 1,
        endChapter: 1,
        refresh: false,
        provider: "claude-code",
        bookId: BOOK_ID,
      }),
    );
  });

  it("disables run actions and prompts to re-import when there is no source url", () => {
    render(<ChaptersTable bookId={BOOK_ID} chapters={chapters} sourceUrl={null} />);

    expect(screen.getByText(/re-import this book/i)).toBeInTheDocument();
    // Row 2 has beats, so Narrate is gated only by the missing source, not by the beat state.
    const menu = openRowMenu(1);
    expect(menu.getByRole("menuitem", { name: "Re-extract beats" })).toBeDisabled();
    expect(menu.getByRole("menuitem", { name: "Narrate" })).toBeDisabled();
  });
});
