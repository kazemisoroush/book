import { apiClient } from "@/lib/api/client";
import { getApiBaseUrl } from "@/lib/config";

import type { components } from "@/lib/api/schema";

export type BookDetail = components["schemas"]["BookDetail"];
export type CharacterInfo = components["schemas"]["CharacterInfo"];
export type ChapterSummary = components["schemas"]["ChapterSummary"];
export type RunStatus = components["schemas"]["RunStatusResponse"];

export const WORKFLOWS = ["parse", "ai", "characters"] as const;
export type Workflow = (typeof WORKFLOWS)[number];

export async function fetchBook(id: string): Promise<BookDetail> {
  const { data, error } = await apiClient().GET("/books/{book_id}", {
    params: { path: { book_id: id } },
  });
  if (error || !data) throw new Error("Could not load the book.");
  return data;
}

export async function fetchFiles(id: string): Promise<string[]> {
  const { data, error } = await apiClient().GET("/books/{book_id}/files", {
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
};

export async function startRun(input: StartRunInput): Promise<RunStatus> {
  const { data, error } = await apiClient().POST("/workflows/{name}/runs", {
    params: { path: { name: input.workflow } },
    body: {
      url: input.url,
      start_chapter: input.startChapter,
      end_chapter: input.endChapter ?? null,
      refresh: input.refresh,
      provider: input.provider ?? null,
    },
  });
  if (error || !data) throw new Error("Could not start the run.");
  return data;
}

export async function getRun(runId: string): Promise<RunStatus> {
  const { data, error } = await apiClient().GET("/runs/{run_id}", {
    params: { path: { run_id: runId } },
  });
  if (error || !data) throw new Error("Could not read the run.");
  return data;
}

// The Server-Sent Events endpoint for a run's logs. Data access owns how the
// backend is reached, including the streaming URL that openapi-fetch cannot type.
export function runLogsUrl(runId: string): string {
  return `${getApiBaseUrl()}/runs/${encodeURIComponent(runId)}/logs`;
}

// A cast character has a recorded voice; the count drives the casting progress.
export function castCount(book: BookDetail): number {
  return Object.keys(book.voice_assignments).length;
}
