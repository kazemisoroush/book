import { apiClient } from "@/lib/api/client";

import type { components } from "@/lib/api/schema";

export type BookDetail = components["schemas"]["BookDetail"];
export type CharacterInfo = components["schemas"]["CharacterInfo"];
export type ChapterSummary = components["schemas"]["ChapterSummary"];
export type RunStatus = components["schemas"]["RunStatusResponse"];
export type RunLogs = components["schemas"]["RunLogsResponse"];
export type RunSummary = components["schemas"]["RunSummary"];

export const WORKFLOWS = [
  "parse",
  "ai",
  "characters",
  "tts",
  "ambient",
  "sfx",
  "music",
  "mix",
] as const;
export type Workflow = (typeof WORKFLOWS)[number];

export async function fetchBook(id: string): Promise<BookDetail> {
  const { data, error } = await (await apiClient()).GET("/books/{book_id}", {
    params: { path: { book_id: id } },
  });
  if (error || !data) throw new Error("Could not load the book.");
  return data;
}

export async function fetchFiles(id: string): Promise<string[]> {
  const { data, error } = await (await apiClient()).GET("/books/{book_id}/files", {
    params: { path: { book_id: id } },
  });
  if (error || !data) throw new Error("Could not load the artifacts.");
  return data.files;
}

export type StartRunInput = {
  workflow: Workflow;
  url: string;
  startChapter: number;
  endChapter?: number;
  refresh: boolean;
  provider?: string;
  bookId?: string;
};

export async function startRun(input: StartRunInput): Promise<RunStatus> {
  const { data, error } = await (await apiClient()).POST("/workflows/{name}/runs", {
    params: { path: { name: input.workflow } },
    body: {
      url: input.url,
      start_chapter: input.startChapter,
      end_chapter: input.endChapter ?? null,
      refresh: input.refresh,
      provider: input.provider ?? null,
      book_id: input.bookId ?? null,
    },
  });
  if (error || !data) throw new Error("Could not start the run.");
  return data;
}

// Fetch the runs recorded for a book (oldest first), so the chapters table can show per-chapter
// state. A run left running past the worker cap is reported as failed.
export async function fetchBookRuns(id: string): Promise<RunSummary[]> {
  const { data, error } = await (await apiClient()).GET("/books/{book_id}/runs", {
    params: { path: { book_id: id } },
  });
  if (error || !data) throw new Error("Could not load the runs.");
  return data.runs;
}

export async function getRun(runId: string): Promise<RunStatus> {
  const { data, error } = await (await apiClient()).GET("/runs/{run_id}", {
    params: { path: { run_id: runId } },
  });
  if (error || !data) throw new Error("Could not read the run.");
  return data;
}

// Fetch a page of a run's logs from *cursor* onward, which callers poll and pass back since Lambda cannot hold a long-lived log stream.
export async function fetchRunLogs(
  runId: string,
  cursor: number,
): Promise<RunLogs> {
  const { data, error } = await (await apiClient()).GET("/runs/{run_id}/logs", {
    params: { path: { run_id: runId }, query: { cursor } },
  });
  if (error || !data) throw new Error("Could not read the run logs.");
  return data;
}

// A cast character has a recorded voice; the count drives the casting progress.
export function castCount(book: BookDetail): number {
  return Object.keys(book.voice_assignments).length;
}
