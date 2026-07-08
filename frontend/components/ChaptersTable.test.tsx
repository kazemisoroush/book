import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/useRunLogs", () => ({
  useRunLogs: () => ({ lines: [], finalStatus: null }),
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

const chapters: ChapterSummary[] = [
  { number: 1, title: "The garret", beats: 0 },
  { number: 2, title: "The tavern", beats: 12 },
];

const URL = "https://www.gutenberg.org/cache/epub/2554/pg2554-images.zip";

describe("ChaptersTable", () => {
  it("shows a row per chapter with its beats and the fitting action", () => {
    render(<ChaptersTable chapters={chapters} sourceUrl={URL} />);

    expect(screen.getByText("The garret")).toBeInTheDocument();
    expect(screen.getByText("The tavern")).toBeInTheDocument();
    expect(screen.getByText("12 beats")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Extract beats" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Narrate" })).toBeInTheDocument();
  });

  it("extracts beats for the chapter that has none", async () => {
    render(<ChaptersTable chapters={chapters} sourceUrl={URL} />);

    fireEvent.click(screen.getByRole("button", { name: "Extract beats" }));

    await waitFor(() =>
      expect(startRun).toHaveBeenCalledWith({
        workflow: "ai",
        url: URL,
        startChapter: 1,
        endChapter: 1,
        refresh: false,
        provider: "claude-code",
      }),
    );
  });

  it("disables actions and prompts to re-import when there is no source url", () => {
    render(<ChaptersTable chapters={chapters} sourceUrl={null} />);

    expect(screen.getByText(/re-import this book/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Extract beats" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Narrate" })).toBeDisabled();
  });
});
