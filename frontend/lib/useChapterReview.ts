"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchChapter, patchBeat, type ChapterDetail } from "@/lib/studio";

// The fields a reviewer can change on a beat. Narrower than the API's BeatPatch: text and emotion
// are always strings here (only the speaker can be cleared to the narrator, via null).
export type BeatEdit = { character_id?: number | null; text?: string; emotion?: string };

export type ReviewState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; chapter: ChapterDetail };

// Per-beat save progress. On error the attempted change is kept so a Retry can resend it, rather
// than dropping the reviewer's edit.
export type BeatSave =
  | { state: "saving" }
  | { state: "saved" }
  | { state: "error"; change: BeatEdit };

const SAVED_LINGER_MS = 1600;

// Load a chapter for the attribution review and save beat edits optimistically: the beat updates
// immediately and its new value stays put. A failure surfaces an error to retry.
export function useChapterReview(bookId: string, number: number) {
  const [state, setState] = useState<ReviewState>({ status: "loading" });
  const [saves, setSaves] = useState<Record<number, BeatSave>>({});
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetchChapter(bookId, number)
      .then((chapter) => {
        if (!cancelled) setState({ status: "ready", chapter });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error", message: "Could not reach the studio API." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, number]);

  // Clear any pending "saved" timers on unmount.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      Object.values(pending).forEach(clearTimeout);
    };
  }, []);

  const saveBeat = useCallback(
    async (index: number, change: BeatEdit) => {
      clearTimeout(timers.current[index]);
      setSaves((prev) => ({ ...prev, [index]: { state: "saving" } }));

      // Apply the change straight away so the edit is visible while the write is in flight.
      setState((prev) => patchLocalBeat(prev, index, (beat) => ({ ...beat, ...change })));

      try {
        const saved = await patchBeat(bookId, number, index, change);
        // Reconcile with the server's beat (e.g. the resolved character_name).
        setState((prev) => patchLocalBeat(prev, index, () => saved));
        setSaves((prev) => ({ ...prev, [index]: { state: "saved" } }));
        timers.current[index] = setTimeout(() => {
          setSaves((prev) => withoutKey(prev, index));
        }, SAVED_LINGER_MS);
      } catch {
        setSaves((prev) => ({ ...prev, [index]: { state: "error", change } }));
      }
    },
    [bookId, number],
  );

  return { state, saves, saveBeat };
}

function patchLocalBeat(
  prev: ReviewState,
  index: number,
  update: (beat: ChapterDetail["beats"][number]) => ChapterDetail["beats"][number],
): ReviewState {
  if (prev.status !== "ready") return prev;
  const beats = prev.chapter.beats.map((beat) => (beat.index === index ? update(beat) : beat));
  return { status: "ready", chapter: { ...prev.chapter, beats } };
}

function withoutKey(saves: Record<number, BeatSave>, index: number): Record<number, BeatSave> {
  const next = { ...saves };
  delete next[index];
  return next;
}
