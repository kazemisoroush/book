"use client";

import { useState } from "react";

import { WORKFLOWS, type Workflow } from "@/lib/studio";
import { useRunLogs } from "@/lib/useRunLogs";
import { useStartRun } from "@/lib/useStartRun";

import { LogConsole } from "./LogConsole";

export function RunPanel({ defaultUrl }: { defaultUrl?: string }) {
  const [workflow, setWorkflow] = useState<Workflow>("ai");
  const [url, setUrl] = useState(defaultUrl ?? "");
  const [startChapter, setStartChapter] = useState(1);
  const [endChapter, setEndChapter] = useState("");
  const [provider, setProvider] = useState("claude-code");
  const { run, error, starting, start } = useStartRun();
  const { lines, finalStatus } = useRunLogs(run?.run_id ?? null);

  function onStart(event: React.FormEvent) {
    event.preventDefault();
    void start({
      workflow,
      url,
      startChapter,
      endChapter: endChapter === "" ? undefined : Number(endChapter),
      refresh: true,
      provider: provider || undefined,
    });
  }

  return (
    <div>
      <form className="run-form" onSubmit={onStart}>
        <div className="run-form__row">
          <label className="field">
            <span className="field__label">Workflow</span>
            <select
              className="field__input"
              value={workflow}
              onChange={(e) => setWorkflow(e.target.value as Workflow)}
            >
              {WORKFLOWS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </label>
          <label className="field field--grow">
            <span className="field__label">Gutenberg URL</span>
            <input
              className="field__input"
              placeholder="https://www.gutenberg.org/cache/epub/2197/pg2197-images.zip"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </label>
        </div>
        <div className="run-form__row">
          <label className="field field--narrow">
            <span className="field__label">From ch.</span>
            <input
              className="field__input"
              type="number"
              min={1}
              value={startChapter}
              onChange={(e) => setStartChapter(Number(e.target.value))}
            />
          </label>
          <label className="field field--narrow">
            <span className="field__label">To ch.</span>
            <input
              className="field__input"
              type="number"
              min={1}
              placeholder="end"
              value={endChapter}
              onChange={(e) => setEndChapter(e.target.value)}
            />
          </label>
          <label className="field field--narrow">
            <span className="field__label">Provider</span>
            <input
              className="field__input"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            />
          </label>
          <button className="btn" type="submit" disabled={starting}>
            {starting ? "Starting…" : "Start run"}
          </button>
        </div>
      </form>

      {error && <p className="muted-note muted-note--error">{error}</p>}
      {run && <LogConsole run={run} lines={lines} finalStatus={finalStatus} />}
    </div>
  );
}
