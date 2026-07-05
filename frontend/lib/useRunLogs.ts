"use client";

import { useEffect, useState } from "react";

import { getRun, openRunLogs, type RunStatus } from "@/lib/studio";

// Stream a run's logs over Server-Sent Events. When the stream ends or errors,
// fetch the run's final status once so callers can show the terminal state.
export function useRunLogs(runId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [finalStatus, setFinalStatus] = useState<RunStatus | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLines([]);
    setFinalStatus(null);

    let cancelled = false;
    let finished = false;
    const source = openRunLogs(runId);

    const finish = () => {
      if (finished) return;
      finished = true;
      source.close();
      getRun(runId)
        .then((status) => {
          if (!cancelled) setFinalStatus(status);
        })
        .catch(() => {});
    };

    source.onmessage = (event) => {
      if (!cancelled) setLines((prev) => [...prev, event.data]);
    };
    source.addEventListener("end", finish);
    source.onerror = finish;

    return () => {
      cancelled = true;
      source.close();
    };
  }, [runId]);

  return { lines, finalStatus };
}
