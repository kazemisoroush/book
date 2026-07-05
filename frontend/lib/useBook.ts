"use client";

import { useEffect, useState } from "react";

import { fetchBook, fetchFiles, type BookDetail } from "@/lib/studio";

export type BookState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; book: BookDetail; files: string[] };

// Load a book's detail and its artifact files.
export function useBook(id: string): BookState {
  const [state, setState] = useState<BookState>({ status: "loading" });

  useEffect(() => {
    if (!id) {
      setState({ status: "error", message: "No book selected." });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    Promise.all([fetchBook(id), fetchFiles(id).catch(() => [])])
      .then(([book, files]) => {
        if (!cancelled) setState({ status: "ready", book, files });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error", message: "Could not reach the studio API." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return state;
}
