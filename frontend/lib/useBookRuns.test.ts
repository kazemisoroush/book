import { describe, expect, it } from "vitest";

import type { RunSummary } from "./studio";
import { latestRunByChapter } from "./useBookRuns";

function run(overrides: Partial<RunSummary>): RunSummary {
  return {
    run_id: "r",
    workflow: "ai",
    start_chapter: 1,
    end_chapter: 1,
    state: "succeeded",
    started_at: "t",
    ended_at: null,
    ...overrides,
  };
}

describe("latestRunByChapter", () => {
  it("maps each chapter to the latest run covering it", () => {
    const runs = [
      run({ run_id: "a", start_chapter: 1, end_chapter: 1, state: "failed" }),
      run({ run_id: "b", start_chapter: 1, end_chapter: 1, state: "running" }),
      run({ run_id: "c", start_chapter: 2, end_chapter: 3, state: "succeeded" }),
    ];

    const byChapter = latestRunByChapter(runs);

    expect(byChapter.get(1)?.state).toBe("running"); // b comes after a
    expect(byChapter.get(2)?.state).toBe("succeeded");
    expect(byChapter.get(3)?.state).toBe("succeeded");
    expect(byChapter.get(4)).toBeUndefined();
  });
});
