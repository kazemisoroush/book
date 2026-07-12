"use client";

import { useState } from "react";

import type { Workflow } from "@/lib/studio";
import { useRunLogs } from "@/lib/useRunLogs";
import { useStartRun } from "@/lib/useStartRun";

// The studio runs its AI and TTS through claude-code. Per-user provider choice is M10.
const PROVIDER = "claude-code";

export type ActiveRun = { chapter: number; label: string };

// Start and track per-chapter workflow runs for the chapters table.
export function useChapterRuns(bookId: string, sourceUrl?: string | null) {
  const [active, setActive] = useState<ActiveRun | null>(null);
  const { run, error, starting, start } = useStartRun();
  const { lines, finalStatus } = useRunLogs(run?.run_id ?? null);

  async function runChapter(workflow: Workflow, chapter: number, label: string) {
    if (!sourceUrl) return;
    setActive({ chapter, label });
    await start({
      workflow,
      url: sourceUrl,
      startChapter: chapter,
      endChapter: chapter,
      refresh: false,
      provider: PROVIDER,
      bookId,
    });
  }

  return { active, run, error, starting, lines, finalStatus, runChapter };
}
