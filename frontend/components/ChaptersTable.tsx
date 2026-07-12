"use client";

import { useEffect, useState } from "react";

import type { ChapterSummary, Workflow } from "@/lib/studio";
import { useBookRuns, latestRunByChapter } from "@/lib/useBookRuns";
import { useChapterRuns } from "@/lib/useChapterRuns";

import { LogConsole } from "./LogConsole";

const PER_PAGE = 8;

export function ChaptersTable({
  bookId,
  chapters,
  sourceUrl,
}: {
  bookId: string;
  chapters: ChapterSummary[];
  sourceUrl?: string | null;
}) {
  const [page, setPage] = useState(0);
  const { active, run, error, starting, lines, finalStatus, runChapter } =
    useChapterRuns(bookId, sourceUrl);
  const { runs, reloadRuns } = useBookRuns(bookId);

  // Refresh the recorded runs as soon as a run finishes, so the row state settles immediately.
  useEffect(() => {
    if (finalStatus) reloadRuns();
  }, [finalStatus, reloadRuns]);

  if (chapters.length === 0) {
    return <p className="muted-note">No chapters yet.</p>;
  }

  const pageCount = Math.max(1, Math.ceil(chapters.length / PER_PAGE));
  const rows = chapters.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE);
  const canRun = Boolean(sourceUrl);
  const runByChapter = latestRunByChapter(runs);

  async function start(workflow: Workflow, chapter: number, label: string) {
    await runChapter(workflow, chapter, label);
    reloadRuns();
  }

  return (
    <div>
      {!canRun && (
        <p className="muted-note">
          Re-import this book to extract beats and narrate its chapters.
        </p>
      )}

      <div className="ctable">
        <div className="ctable__row ctable__row--head">
          <span>#</span>
          <span>Chapter</span>
          <span className="ctable__progress-label">Progress</span>
          <span className="ctable__action-label">Action</span>
        </div>

        {rows.map((chapter) => {
          const beats = chapter.beats ?? 0;
          const hasBeats = beats > 0;
          const runState = runByChapter.get(chapter.number)?.state;
          const isRunning =
            runState === "running" || (starting && active?.chapter === chapter.number);
          const failed = runState === "failed";
          return (
            <div className="ctable__row" key={chapter.number}>
              <div className="cnum">{String(chapter.number).padStart(2, "0")}</div>
              <div className="ctitle">
                {chapter.title || `Chapter ${chapter.number}`}
                <small>{hasBeats ? `${beats} beats` : "parsed"}</small>
              </div>
              <Stepper hasBeats={hasBeats} running={isRunning} failed={failed} />
              <div className="cact">
                {isRunning ? (
                  <span className="run-badge run-badge--running">Running&hellip;</span>
                ) : (
                  <>
                    {failed && <span className="run-badge run-badge--failed">Failed</span>}
                    {hasBeats ? (
                      <button
                        className="btn-act"
                        disabled={!canRun || starting}
                        onClick={() => start("tts", chapter.number, "Narrating")}
                      >
                        Narrate
                      </button>
                    ) : (
                      <button
                        className="btn-act"
                        disabled={!canRun || starting}
                        onClick={() => start("ai", chapter.number, "Extracting beats for")}
                      >
                        {failed ? "Retry" : "Extract beats"}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="cpager">
        <span className="muted-note">
          {page * PER_PAGE + 1}&ndash;{Math.min((page + 1) * PER_PAGE, chapters.length)} of{" "}
          {chapters.length} chapters
        </span>
        <div className="cpager__btns">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            &larr; Prev
          </button>
          <button disabled={page >= pageCount - 1} onClick={() => setPage((p) => p + 1)}>
            Next &rarr;
          </button>
        </div>
      </div>

      {run && active && (
        <div className="run-active">
          <p className="run-active__head">
            {active.label} chapter {active.chapter}
          </p>
          <LogConsole run={run} lines={lines} finalStatus={finalStatus} />
        </div>
      )}
      {error && <p className="muted-note muted-note--error">{error}</p>}
    </div>
  );
}

function Stepper({
  hasBeats,
  running,
  failed,
}: {
  hasBeats: boolean;
  running: boolean;
  failed: boolean;
}) {
  const beatsState = running ? "active" : hasBeats ? "done" : failed ? "failed" : "active";
  const steps: { label: string; state: "done" | "active" | "todo" | "failed" }[] = [
    { label: "Parsed", state: "done" },
    { label: "Beats", state: beatsState },
    { label: "Narrate", state: "todo" },
    { label: "Mix", state: "todo" },
  ];
  return (
    <div className="steps">
      {steps.map((step) => (
        <div key={step.label} className={`step step--${step.state}`}>
          <span className="dot" />
          <span className="step__l">{step.label}</span>
        </div>
      ))}
    </div>
  );
}
