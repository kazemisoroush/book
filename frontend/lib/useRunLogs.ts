"use client";

import { useEffect, useState } from "react";

import { getRun, runLogsUrl, type RunStatus } from "@/lib/studio";

// Stream a run's logs over Server-Sent Events. When the run signals it is done,
// fetch its final status so callers can show the terminal state.
export function useRunLogs(runId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [finalStatus, setFinalStatus] = useState<RunStatus | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLines([]);
    setFinalStatus(null);

    const source = new EventSource(runLogsUrl(runId));
    source.onmessage = (event) => {
      setLines((prev) => [...prev, event.data]);
    };
    source.addEventListener("end", () => {
      source.close();
      getRun(runId)
        .then(setFinalStatus)
        .catch(() => setFinalStatus(null));
    });
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [runId]);

  return { lines, finalStatus };
}
