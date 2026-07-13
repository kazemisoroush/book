import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/studio", () => ({
  fetchChapter: vi.fn(),
  patchBeat: vi.fn(),
}));

import { fetchChapter, patchBeat } from "@/lib/studio";

import { useChapterReview } from "./useChapterReview";

const CHAPTER = {
  number: 1,
  title: "One",
  sections: [{ text: "He walked out.", section_type: null }],
  beats: [
    { index: 0, character_id: 1, character_name: "Narrator", beat_type: "narration",
      text: "He walked out.", emotion: "measured" },
  ],
  cast: [
    { id: 1, name: "Narrator", count: 1 },
    { id: 2, name: "Nastasya", count: 0 },
  ],
};

beforeEach(() => {
  vi.mocked(fetchChapter).mockReset();
  vi.mocked(patchBeat).mockReset();
});

describe("useChapterReview", () => {
  it("loads a chapter", async () => {
    vi.mocked(fetchChapter).mockResolvedValue(structuredClone(CHAPTER));
    const { result } = renderHook(() => useChapterReview("b", 1));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));
  });

  it("applies a reassignment optimistically and reconciles with the server", async () => {
    vi.mocked(fetchChapter).mockResolvedValue(structuredClone(CHAPTER));
    vi.mocked(patchBeat).mockResolvedValue({
      index: 0, character_id: 2, character_name: "Nastasya", beat_type: "narration",
      text: "He walked out.", emotion: "measured",
    });
    const { result } = renderHook(() => useChapterReview("b", 1));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await act(async () => {
      await result.current.saveBeat(0, { character_id: 2 });
    });

    const state = result.current.state;
    expect(state.status).toBe("ready");
    if (state.status === "ready") {
      expect(state.chapter.beats[0].character_name).toBe("Nastasya");
    }
    expect(result.current.saves[0]?.state).toBe("saved");
  });

  it("keeps the attempted change on failure so it can be retried", async () => {
    vi.mocked(fetchChapter).mockResolvedValue(structuredClone(CHAPTER));
    vi.mocked(patchBeat).mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useChapterReview("b", 1));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await act(async () => {
      await result.current.saveBeat(0, { emotion: "frantic" });
    });

    const save = result.current.saves[0];
    expect(save?.state).toBe("error");
    if (save?.state === "error") expect(save.change).toEqual({ emotion: "frantic" });
    // The optimistic edit is not thrown away.
    const state = result.current.state;
    if (state.status === "ready") expect(state.chapter.beats[0].emotion).toBe("frantic");
  });
});
