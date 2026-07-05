"use client";

import { useEffect, useState } from "react";

import { getApiBaseUrl } from "@/lib/config";

// Stream a run's logs over Server-Sent Events, closing when the run signals it is done.
export function useRunLogs(runId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setLines([]);
    setDone(false);

    const source = new EventSource(
      `${getApiBaseUrl()}/runs/${encodeURIComponent(runId)}/logs`,
    );
    source.onmessage = (event) => {
      setLines((prev) => [...prev, event.data]);
    };
    source.addEventListener("end", () => {
      setDone(true);
      source.close();
    });
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [runId]);

  return { lines, done };
}
