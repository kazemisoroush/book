"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchBookRuns, type RunSummary } from "@/lib/studio";

// Poll a book's runs while any is still running, so the chapters table reflects live state.
export function useBookRuns(bookId: string) {
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const reload = useCallback(() => {
    let cancelled = false;
    fetchBookRuns(bookId)
      .then((next) => {
        if (!cancelled) setRuns(next);
      })
      .catch(() => {
        // Keep the last known runs on a transient read failure.
      });
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  useEffect(() => reload(), [reload]);

  useEffect(() => {
    if (!runs.some((run) => run.state === "running")) return;
    const timer = setInterval(reload, 4000);
    return () => clearInterval(timer);
  }, [runs, reload]);

  return { runs, reloadRuns: reload };
}

// The latest run covering each chapter number, so a row can show its state.
export function latestRunByChapter(runs: RunSummary[]): Map<number, RunSummary> {
  const byChapter = new Map<number, RunSummary>();
  for (const run of runs) {
    const start = run.start_chapter ?? 1;
    const end = run.end_chapter ?? start;
    for (let number = start; number <= end; number += 1) {
      byChapter.set(number, run);
    }
  }
  return byChapter;
}
