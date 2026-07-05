"use client";

import { useEffect, useState } from "react";

import { fetchRunLogs, getRun, type RunStatus } from "@/lib/studio";

const POLL_MS = 1500;

// Poll a run's logs from a cursor until the run is done, then fetch its final
// status so callers can show the terminal state.
export function useRunLogs(runId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [finalStatus, setFinalStatus] = useState<RunStatus | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLines([]);
    setFinalStatus(null);

    let cancelled = false;
    let cursor = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const page = await fetchRunLogs(runId!, cursor);
        if (cancelled) return;
        if (page.lines.length > 0) {
          setLines((prev) => [...prev, ...page.lines]);
        }
        cursor = page.cursor;
        if (page.done) {
          const status = await getRun(runId!).catch(() => null);
          if (!cancelled) setFinalStatus(status);
          return;
        }
      } catch {
        // Transient error; keep polling.
      }
      if (!cancelled) timer = setTimeout(poll, POLL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  return { lines, finalStatus };
}
