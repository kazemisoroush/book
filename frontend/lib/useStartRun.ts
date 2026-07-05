"use client";

import { useState } from "react";

import { startRun, type RunStatus, type StartRunInput } from "@/lib/studio";

// Start a workflow run and track the in-flight and error state.
export function useStartRun() {
  const [run, setRun] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  async function start(input: StartRunInput) {
    setError(null);
    setStarting(true);
    try {
      setRun(await startRun(input));
    } catch {
      setError("Could not start the run. Is the API running?");
    } finally {
      setStarting(false);
    }
  }

  return { run, error, starting, start };
}
